import threading
import time
import os
import shutil
import random
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError, expect
from .models import AutomationLog, ShopifyAccount

INITIAL_URL = "https://admin.shopify.com/store/nsc1g4-gf/apps/tiktok-ads-2/setup/marketing?country=BR"
LOGIN_EMAIL = "estela-altoe@tuamaeaquelaursa.com"
LOGIN_PASSWORD = "respepek12"
BRAVE_PATH = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
BRAVE_USER_DATA = r"C:\Users\hugom\AppData\Local\BraveSoftware\Brave-Browser\User Data"
STATE_FILE = "shopify_auth_state.json"

class Automator:
    def __init__(self, stop_event, cdp_endpoint=None):
        self.stop_event = stop_event
        self.cdp_endpoint = cdp_endpoint
        self.accounts_created = 0
        self.iframe = None

    def log(self, message, level="INFO"):
        try:
            AutomationLog.objects.create(message=message, level=level)
        except Exception:
            print(f"LOG {level}: {message}")

    def create_account_record(self, email, phone):
        try:
            ShopifyAccount.objects.create(email=email, phone=phone)
            self.accounts_created += 1
            self.log(f"✅ Conta criada com sucesso! Total: {self.accounts_created} | Email: {email} | Telefone: {phone}", "SUCCESS")
        except Exception as e:
            self.log(f"❌ Falha ao salvar conta {email} / {phone}: {e}", "ERROR")

    def generate_phone(self):
        """Generate a random Brazilian phone number with DDD"""
        ddd = str(random.randint(11, 99))
        number = str(random.randint(900000000, 999999999))
        return ddd + number

    def setup_browser_context(self, playwright):
        """Setup browser context with session persistence - usando Brave"""
        
        if self.cdp_endpoint:
            try:
                self.log(f'🔌 Conectando ao endpoint CDP: {self.cdp_endpoint}')
                browser = playwright.chromium.connect_over_cdp(self.cdp_endpoint)
                contexts = getattr(browser, 'contexts', [])
                if contexts:
                    context = contexts[0]
                    page = context.pages[0] if context.pages else context.new_page()
                else:
                    context = browser.new_context()
                    page = context.new_page()
                return browser, context, page
            except Exception as e:
                self.log(f'⚠️ CDP connection failed: {e}', "WARNING")

        if os.path.exists(STATE_FILE):
            self.log(f'📂 Carregando sessão salva de {STATE_FILE}')
            browser = playwright.chromium.launch(
                headless=False,
                executable_path=BRAVE_PATH
            )
            context = browser.new_context(storage_state=STATE_FILE)
            page = context.new_page()
            return browser, context, page

        if os.path.exists(BRAVE_USER_DATA):
            try:
                copy_dir = os.path.join(os.getcwd(), 'brave-profile-copy')
                if os.path.exists(copy_dir):
                    shutil.rmtree(copy_dir)
                
                self.log(f'📋 Copiando perfil Brave...')
                shutil.copytree(BRAVE_USER_DATA, copy_dir)
                
                self.log(f'🚀 Iniciando Brave com perfil persistente')
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=copy_dir, 
                    headless=False,
                    executable_path=BRAVE_PATH,
                    args=['--disable-blink-features=AutomationControlled']
                )
                page = context.new_page() if not context.pages else context.pages[0]
                return None, context, page
            except Exception as e:
                self.log(f'⚠️ Falha ao copiar perfil Brave: {e}', "WARNING")

        self.log('🚀 Iniciando Brave novo')
        browser = playwright.chromium.launch(
            headless=False,
            executable_path=BRAVE_PATH,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context()
        page = context.new_page()
        return browser, context, page

    def get_iframe(self, page):
        """Get the TikTok iframe"""
        try:
            self.log("🔍 Procurando iframe do TikTok...")
            iframe_element = page.frame(name='app-iframe')
            if not iframe_element:
                iframe_element = page.frame_locator('iframe[title="TikTok"]').first
            if iframe_element:
                self.log("✅ Iframe do TikTok encontrado!")
                return iframe_element
            else:
                self.log("❌ Iframe não encontrado", "ERROR")
                return None
        except Exception as e:
            self.log(f"❌ Erro ao encontrar iframe: {e}", "ERROR")
            return None

    def wait_for_element_in_iframe(self, iframe, selector, description, timeout=15000):
        """Wait for element to be visible inside iframe"""
        try:
            element = iframe.locator(selector).first
            element.wait_for(state='visible', timeout=timeout)
            self.log(f"✅ Elemento encontrado no iframe: {description}")
            return element
        except Exception:
            self.log(f"⚠️ Elemento não encontrado no iframe: {description}", "WARNING")
            return None

    def click_element_in_iframe(self, iframe, selector, description, timeout=10000):
        """Click element inside iframe with retry"""
        try:
            element = self.wait_for_element_in_iframe(iframe, selector, description, timeout)
            if element:
                element.scroll_into_view_if_needed()
                time.sleep(0.3)
                element.click()
                self.log(f"✅ Clicou no iframe: {description}")
                return True
            return False
        except Exception as e:
            self.log(f"❌ Falha ao clicar no iframe {description}: {e}", "ERROR")
            return False

    def is_element_visible(self, iframe, selector):
        """Check if an element is visible"""
        try:
            element = iframe.locator(selector).first
            return element.count() > 0 and element.is_visible()
        except Exception:
            return False

    def is_card_truly_expanded(self, iframe):
        """Check if the card is truly expanded by looking at actual content"""
        try:
            # Verifica se o conteúdo do card está visível
            content_selectors = [
                '.global-setting-content',
                '.list-content',
                '.account-card',
                '.bc-item',
                '#ttamCard'
            ]
            
            for selector in content_selectors:
                try:
                    element = iframe.locator(selector).first
                    if element.count() > 0 and element.is_visible():
                        self.log("✅ Card realmente expandido (conteúdo visível)")
                        return True
                except Exception:
                    continue
            
            # Verifica se o collapsible está com aria-hidden false
            try:
                collapsible = iframe.locator('#onboarding-setting-collapsible').first
                if collapsible.count() > 0:
                    aria_hidden = collapsible.get_attribute('aria-hidden')
                    if aria_hidden == 'false':
                        self.log("✅ Card realmente expandido (aria-hidden=false)")
                        return True
            except Exception:
                pass
            
            self.log("⚠️ Card não está realmente expandido")
            return False
            
        except Exception as e:
            self.log(f"⚠️ Erro ao verificar expansão real: {e}", "WARNING")
            return False

    def force_expand_card(self, iframe):
        """Force expand the card regardless of current state"""
        self.log("🔧 FORÇANDO expansão do card...")
        
        # Primeiro, tenta encontrar e clicar no ícone de expandir
        expand_icon_selectors = [
            'fieldset.onboarding-card.ttam span.expand-icon',
            '.onboarding-card.ttam span.expand-icon',
            '.onboarding-card.ttam .expand-icon',
            'span.expand-icon',
            '.expand-icon'
        ]
        
        for selector in expand_icon_selectors:
            try:
                icon = iframe.locator(selector).first
                if icon.count() > 0:
                    icon.scroll_into_view_if_needed()
                    time.sleep(0.5)
                    icon.click()
                    self.log(f"✅ Clique no ícone de expandir: {selector}")
                    time.sleep(1.5)
                    
                    # Verifica se expandiu
                    if self.is_card_truly_expanded(iframe):
                        self.log("✅ Card expandido com sucesso via ícone!")
                        return True
            except Exception as e:
                self.log(f"⚠️ Falha ao tentar expandir via {selector}: {e}", "WARNING")
                continue
        
        # Tenta clicar no título do card
        try:
            title = iframe.locator('.onboarding-card.ttam .onboarding-card-title').first
            if title.count() > 0:
                title.scroll_into_view_if_needed()
                title.click()
                self.log("✅ Clique no título do card")
                time.sleep(1.5)
                
                if self.is_card_truly_expanded(iframe):
                    self.log("✅ Card expandido com sucesso via título!")
                    return True
        except Exception as e:
            self.log(f"⚠️ Falha ao tentar expandir via título: {e}", "WARNING")
        
        # JavaScript para forçar expansão
        try:
            iframe.evaluate("""
                () => {
                    // Tenta encontrar o ícone de expandir
                    const expandIcon = document.querySelector('fieldset.onboarding-card.ttam span.expand-icon, .onboarding-card.ttam .expand-icon');
                    if (expandIcon) {
                        expandIcon.click();
                        return true;
                    }
                    // Tenta encontrar o título
                    const title = document.querySelector('.onboarding-card.ttam .onboarding-card-title');
                    if (title) {
                        title.click();
                        return true;
                    }
                    return false;
                }
            """)
            self.log("✅ Tentativa de expansão via JavaScript")
            time.sleep(1.5)
            
            if self.is_card_truly_expanded(iframe):
                self.log("✅ Card expandido com sucesso via JavaScript!")
                return True
        except Exception as e:
            self.log(f"⚠️ Falha na expansão via JavaScript: {e}", "WARNING")
        
        self.log("❌ Não foi possível expandir o card", "ERROR")
        return False

    def find_and_click_create_new(self, iframe):
        """Find and click 'Criar novo' button in the TikTok card"""
        
        # Lista de seletores para o botão Criar novo
        create_new_selectors = [
            'fieldset.onboarding-card.ttam button:has-text("Criar novo")',
            '.onboarding-card.ttam button:has-text("Criar novo")',
            '.onboarding-card.ttam .Polaris-Link:has-text("Criar novo")',
            'button:has-text("Criar novo")',
            '.Polaris-Link:has-text("Criar novo")'
        ]
        
        # Primeiro, tenta encontrar o botão diretamente
        for selector in create_new_selectors:
            if self.is_element_visible(iframe, selector):
                self.log("✅ Botão 'Criar novo' está visível!")
                return self.click_element_in_iframe(iframe, selector, "Criar novo (visível)", 5000)
        
        # Se não encontrou, verifica se o card está realmente expandido
        if not self.is_card_truly_expanded(iframe):
            self.log("⚠️ Card não está expandido, forçando expansão...", "WARNING")
            if self.force_expand_card(iframe):
                time.sleep(1.5)
                # Após expandir, procura novamente
                for selector in create_new_selectors:
                    if self.is_element_visible(iframe, selector):
                        self.log("✅ Botão 'Criar novo' encontrado após expansão!")
                        return self.click_element_in_iframe(iframe, selector, "Criar novo (após expansão)", 5000)
        else:
            self.log("⚠️ Card está expandido mas botão não visível, tentando outros métodos...", "WARNING")
            
            # Tenta encontrar o botão "Alterar conta" primeiro
            change_selectors = [
                'fieldset.onboarding-card.ttam button:has-text("Alterar conta")',
                '.onboarding-card.ttam button:has-text("Alterar conta")',
                'button:has-text("Alterar conta")'
            ]
            
            for selector in change_selectors:
                if self.is_element_visible(iframe, selector):
                    self.log("✅ Botão 'Alterar conta' encontrado!")
                    if self.click_element_in_iframe(iframe, selector, "Alterar conta", 5000):
                        time.sleep(1.5)
                        # Após clicar em Alterar conta, procura Criar novo
                        for create_selector in create_new_selectors:
                            if self.is_element_visible(iframe, create_selector):
                                self.log("✅ Botão 'Criar novo' encontrado após 'Alterar conta'!")
                                return self.click_element_in_iframe(iframe, create_selector, "Criar novo (após Alterar conta)", 5000)
        
        return False

    def find_and_click_alterar_conta(self, iframe):
        """Find and click 'Alterar conta' button in the TikTok card"""
        change_selectors = [
            'fieldset.onboarding-card.ttam button:has-text("Alterar conta")',
            '.onboarding-card.ttam button:has-text("Alterar conta")',
            'button:has-text("Alterar conta")',
            '.Polaris-Button:has-text("Alterar conta")'
        ]
        
        for selector in change_selectors:
            if self.is_element_visible(iframe, selector):
                self.log("✅ Botão 'Alterar conta' encontrado!")
                return self.click_element_in_iframe(iframe, selector, "Alterar conta", 5000)
        
        return False

    def fill_phone_in_modal(self, iframe, phone):
        """Fill phone number in the TikTok modal"""
        try:
            self.log(f"🔍 Procurando campo de telefone para preencher: {phone}")
            
            # Aguarda o modal abrir
            time.sleep(2)
            
            # Tenta encontrar o campo de telefone
            phone_selectors = [
                'input[name="mobile"]',
                'input[type="tel"]',
                '#phoneInput input',
                '.account-center-input-item input',
                'input[placeholder*="telefone" i]',
                'input[placeholder*="phone" i]',
                'input[class*="phone"]',
                'input[class*="mobile"]'
            ]
            
            for selector in phone_selectors:
                try:
                    phone_input = iframe.locator(selector).first
                    if phone_input.count() > 0 and phone_input.is_visible():
                        phone_input.scroll_into_view_if_needed()
                        phone_input.wait_for(state='visible', timeout=3000)
                        phone_input.fill('')
                        time.sleep(0.3)
                        phone_input.fill(phone)
                        value = phone_input.input_value()
                        if value == phone:
                            self.log(f"✅ Telefone preenchido com sucesso: {phone}")
                            return True
                except Exception:
                    continue
            
            self.log("⚠️ Campo de telefone não encontrado", "WARNING")
            return False
            
        except Exception as e:
            self.log(f"❌ Erro ao preencher telefone: {e}", "ERROR")
            return False

    def check_agreement_in_modal(self, iframe):
        """Check the agreement checkbox"""
        try:
            self.log("🔍 Procurando checkbox de concordância...")
            
            checkbox_selectors = [
                '.byted-checkbox-icon',
                'input[type="checkbox"]',
                '.agreement-container input',
                'span.byted-checkbox-icon',
                '.agreement input'
            ]
            
            for selector in checkbox_selectors:
                try:
                    checkbox = iframe.locator(selector).first
                    if checkbox.count() > 0 and checkbox.is_visible():
                        checkbox.scroll_into_view_if_needed()
                        checkbox.wait_for(state='visible', timeout=3000)
                        try:
                            is_checked = checkbox.is_checked()
                        except:
                            is_checked = False
                            
                        if not is_checked:
                            checkbox.check()
                            self.log(f"✅ Checkbox marcado")
                            return True
                        else:
                            self.log("✅ Checkbox já estava marcado")
                            return True
                except Exception:
                    continue
            
            self.log("⚠️ Checkbox não encontrado, continuando...", "WARNING")
            return True
            
        except Exception as e:
            self.log(f"⚠️ Erro ao marcar checkbox: {e}", "WARNING")
            return True

    def click_submit_in_modal(self, iframe):
        """Click the submit button"""
        try:
            self.log("🔍 Procurando botão de envio...")
            
            submit_selectors = [
                'button:has-text("Inscrever e conectar")',
                'button.byted-btn-primary:has-text("Inscrever")',
                'button:has-text("Conectar")',
                'button[type="submit"]'
            ]
            
            for selector in submit_selectors:
                try:
                    submit_btn = iframe.locator(selector).first
                    if submit_btn.count() > 0 and submit_btn.is_visible():
                        submit_btn.scroll_into_view_if_needed()
                        submit_btn.wait_for(state='visible', timeout=3000)
                        time.sleep(0.5)
                        submit_btn.click()
                        self.log(f"✅ Botão de envio clicado")
                        return True
                except Exception:
                    continue
            
            self.log("⚠️ Botão de envio não encontrado", "WARNING")
            return False
            
        except Exception as e:
            self.log(f"❌ Erro ao clicar no botão de envio: {e}", "ERROR")
            return False

    def create_new_account(self, page):
        """Create a new account working inside the iframe"""
        try:
            # Get the iframe
            iframe = self.get_iframe(page)
            if not iframe:
                self.log("❌ Não foi possível acessar o iframe", "ERROR")
                return False
            
            # Generate phone number
            phone = self.generate_phone()
            self.log(f"📝 Criando nova conta com telefone: {phone}")
            
            # Verifica se já existe conta (presença do botão "Alterar conta")
            has_account = self.is_element_visible(iframe, 'button:has-text("Alterar conta")')
            
            if has_account:
                self.log("📋 Fluxo com conta existente detectado")
                # Clica em Alterar conta
                if not self.find_and_click_alterar_conta(iframe):
                    self.log("⚠️ Não conseguiu clicar em Alterar conta", "WARNING")
                    return False
                time.sleep(1.5)
                # Depois clica em Criar novo
                if not self.find_and_click_create_new(iframe):
                    self.log("⚠️ Não conseguiu clicar em Criar novo após Alterar conta", "WARNING")
                    return False
            else:
                self.log("🆕 Fluxo sem conta existente")
                # Tenta clicar diretamente em Criar novo
                if not self.find_and_click_create_new(iframe):
                    self.log("⚠️ Não conseguiu clicar em Criar novo", "WARNING")
                    return False
            
            time.sleep(2)
            
            # Preenche telefone
            phone_filled = False
            for attempt in range(3):
                if self.fill_phone_in_modal(iframe, phone):
                    phone_filled = True
                    break
                self.log(f"⚠️ Tentativa {attempt + 1} de preencher telefone falhou", "WARNING")
                time.sleep(1)
            
            if not phone_filled:
                self.log("❌ Não foi possível preencher o telefone", "ERROR")
                return False
            
            time.sleep(0.5)
            
            # Marca checkbox
            self.check_agreement_in_modal(iframe)
            
            time.sleep(0.5)
            
            # Envia
            submitted = False
            for attempt in range(3):
                if self.click_submit_in_modal(iframe):
                    submitted = True
                    break
                self.log(f"⚠️ Tentativa {attempt + 1} de enviar falhou", "WARNING")
                time.sleep(1)
            
            if not submitted:
                self.log("❌ Não foi possível enviar o formulário", "ERROR")
                return False
            
            time.sleep(3)
            
            # Sucesso!
            self.create_account_record(LOGIN_EMAIL, phone)
            return True
            
        except Exception as e:
            self.log(f"❌ Erro ao criar conta: {e}", "ERROR")
            import traceback
            self.log(traceback.format_exc(), "ERROR")
            return False

    def wait_for_tiktok_section(self, page):
        """Wait for TikTok iframe to load"""
        self.log("⏳ Aguardando iframe do TikTok carregar (até 30 segundos)...")
        
        try:
            page.wait_for_selector('iframe[title="TikTok"]', timeout=30000)
            self.log("✅ Iframe do TikTok encontrado!")
            
            iframe = self.get_iframe(page)
            if iframe:
                iframe.wait_for_selector('.onboarding-card.ttam', timeout=10000)
                self.log("✅ Card do TikTok carregado!")
                return True
            return False
            
        except PWTimeoutError as e:
            self.log(f"❌ Timeout: Card do TikTok não carregou - {e}", "ERROR")
            return False

    def run(self):
        self.log("🤖 Automação iniciada - Modo contínuo")
        self.log("🔄 O sistema ficará criando contas até você clicar em STOP")
        
        try:
            with sync_playwright() as p:
                browser, context, page = self.setup_browser_context(p)
                
                self.log(f"🌐 Navegando para: {INITIAL_URL}")
                try:
                    page.goto(INITIAL_URL, timeout=60000)
                except Exception as e:
                    self.log(f"⚠️ Erro na navegação: {e}", "WARNING")
                
                time.sleep(5)
                
                current_url = page.url
                self.log(f"📍 URL atual: {current_url}")
                
                if not current_url.startswith('https://admin.shopify.com'):
                    self.log("⚠️ Não está na página admin", "WARNING")
                    if 'login' in current_url.lower():
                        self.log("🔐 Página de login detectada, aguardando login manual...")
                        self.log("👤 Por favor, faça login manualmente no Brave (você tem 5 minutos)")
                        try:
                            page.wait_for_url('**/admin/**', timeout=300000)
                            self.log("✅ Login realizado com sucesso!")
                            if context and hasattr(context, 'storage_state'):
                                context.storage_state(path=STATE_FILE)
                                self.log("💾 Sessão salva para próximas execuções")
                        except PWTimeoutError:
                            self.log("❌ Timeout no login", "ERROR")
                            return
                
                time.sleep(3)
                
                if not self.wait_for_tiktok_section(page):
                    self.log("❌ Não foi possível encontrar o card do TikTok", "ERROR")
                    return
                
                account_number = 1
                while not self.stop_event.is_set():
                    self.log(f"\n{'='*50}")
                    self.log(f"🔄 Iniciando criação da conta #{account_number}")
                    self.log(f"{'='*50}")
                    
                    success = self.create_new_account(page)
                    
                    if success:
                        account_number += 1
                        self.log("⏳ Aguardando 3 segundos antes da próxima conta...")
                        time.sleep(3)
                    else:
                        self.log("⚠️ Falha na criação, tentando novamente em 5 segundos...", "WARNING")
                        time.sleep(5)
                        # Não recarrega a página, apenas tenta novamente
                        continue
                
                self.log(f"\n✅ Automação interrompida pelo usuário")
                self.log(f"📊 Total de contas criadas: {self.accounts_created}")
                
                time.sleep(2)
                try:
                    if context:
                        context.close()
                    if browser:
                        browser.close()
                except Exception:
                    pass
                    
        except Exception as e:
            self.log(f"❌ Erro fatal: {e}", "ERROR")
            import traceback
            self.log(traceback.format_exc(), "ERROR")
        
        self.log('🏁 Automação finalizada')


def discover_cdp_endpoints(port_start=9222, port_end=9232, host='127.0.0.1'):
    """Scan local ports for Brave/Chrome with remote debugging enabled."""
    import urllib.request
    import json
    results = []
    for port in range(port_start, port_end + 1):
        try:
            url = f'http://{host}:{port}/json/version'
            resp = urllib.request.urlopen(url, timeout=0.6)
            data = json.loads(resp.read().decode('utf-8'))
            results.append({
                'port': port,
                'webSocketDebuggerUrl': data.get('webSocketDebuggerUrl'),
                'browser': data.get('Browser'),
                'userAgent': data.get('User-Agent') or data.get('UserAgent')
            })
        except Exception:
            try:
                url2 = f'http://{host}:{port}/json'
                resp2 = urllib.request.urlopen(url2, timeout=0.6)
                arr = json.loads(resp2.read().decode('utf-8'))
                if arr and len(arr) > 0:
                    results.append({
                        'port': port,
                        'webSocketDebuggerUrl': arr[0].get('webSocketDebuggerUrl'),
                        'browser': None
                    })
            except Exception:
                continue
    return results