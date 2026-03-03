#!/usr/bin/env python3

import json
import os
import re
import requests
from bs4 import BeautifulSoup
from twocaptcha import TwoCaptcha
from dotenv import load_dotenv
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

# URL base del sitio (para Referer y warm-up)
DEFAULT_BASE_URL = "https://eleccionescolombia.registraduria.gov.co"
# URL de la página de identificación (GET para cargar formulario y obtener sitekey)
DEFAULT_PAGE_URL = "https://eleccionescolombia.registraduria.gov.co/identificacion"
# API Infovotantes para la consulta real (POST con Bearer = token captcha)
DEFAULT_API_URL = "https://apiweb-eleccionescolombia.infovotantes.com/api/v1/citizen/get-information"
# Sitekey reCAPTCHA del nuevo sitio (fallback si no se detecta en la página)
DEFAULT_SITEKEY = "6Lc9DmgrAAAAAJAjWVhjDy1KSgqzqJikY5z7I9SV"
# Código de elección por defecto cuando election_id == -1
DEFAULT_ELECTION_CODE = "congreso"


class VotingPlaceQuery:
    
    def __init__(self, api_key, logger=None):
        self.api_key = api_key
        self.url = os.getenv("REGISTRADURIA_CENSO_URL", DEFAULT_PAGE_URL)
        self.api_url = os.getenv("REGISTRADURIA_API_URL", DEFAULT_API_URL)
        base_url_env = os.getenv("REGISTRADURIA_BASE_URL", DEFAULT_BASE_URL)
        if base_url_env:
            self.base_url = base_url_env.rstrip('/')
        else:
            parsed = urlparse(self.url)
            self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        self.solver = TwoCaptcha(api_key)
        self.session = requests.Session()
        self.logger = logger

        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': f'{self.base_url}/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
        })
    
    def _log(self, message, level='info'):
        if self.logger:
            if level == 'info':
                self.logger.info(message)
            elif level == 'warning':
                self.logger.warning(message)
            elif level == 'error':
                self.logger.error(message)
            elif level == 'debug':
                self.logger.debug(message)
        else:
            print(message)

    def _apply_playwright_cookies_to_session(self, cookies):
        """Copia las cookies del contexto Playwright a la sesión requests."""
        self.session.cookies.clear()
        for c in cookies:
            domain = c.get('domain')
            path = c.get('path') or '/'
            self.session.cookies.set(c['name'], c['value'], domain=domain, path=path)

    def _get_playwright_proxy(self):
        """Devuelve el dict de proxy para Playwright. Solo server = proxy sin auth (ej. local); server+user+pass = con auth."""
        server = (
            (os.getenv("PLAYWRIGHT_PROXY_SERVER") or os.getenv("OXYLABS_PROXY_SERVER")) or ""
        ).strip()
        username = (
            (os.getenv("PLAYWRIGHT_PROXY_USERNAME") or os.getenv("OXYLABS_PROXY_USERNAME"))
            or ""
        ).strip()
        password = (
            (os.getenv("PLAYWRIGHT_PROXY_PASSWORD") or os.getenv("OXYLABS_PROXY_PASSWORD"))
            or ""
        ).strip()
        if not server:
            return None
        if username and password:
            return {"server": server, "username": username, "password": password}
        return {"server": server}

    def _navigate_and_get_soup(self, page, timeout_ms=20000):
        """Navega a la página de identificación y devuelve (soup, None) o (None, error_message).
        Si la carga devuelve HTTP 4xx/5xx (p. ej. 403), no se devuelve soup para evitar consumir
        captcha en una página de error."""
        try:
            try:
                page.goto(f'{self.base_url}/', timeout=timeout_ms, wait_until='domcontentloaded')
            except Exception:
                pass
            response = page.goto(self.url, timeout=timeout_ms, wait_until='domcontentloaded')
            if not response or response.status >= 400:
                status = getattr(response, 'status', None) if response else None
                err = f"HTTP {status}" if status else "carga fallida"
                self._log(f"✗ La página devolvió error: {err}", 'error')
                return None, err
            html = page.content()
            return BeautifulSoup(html, 'html.parser'), None
        except Exception as e:
            err_msg = str(e)
            self._log(f"✗ Error al navegar: {e}", 'error')
            return None, err_msg

    def _log_proxy_troubleshoot(self, response_status=None):
        """Sugerencia cuando falla la navegación con proxy."""
        if response_status == 403:
            self._log(
                "El proxy devolvió 403 (restricted target). Algunos proveedores (p. ej. Oxylabs) "
                "bloquean dominios .gov: contacta a soporte para solicitar acceso a este sitio.",
                "warning",
            )
        else:
            self._log(
                "Revisa PLAYWRIGHT_PROXY_* o OXYLABS_PROXY_* (server, usuario, contraseña). "
                "Oxylabs: usuario customer-TU_USUARIO-cc-CO. 2Captcha: usuario desde api.2captcha.com/proxy?key=API_KEY.",
                "warning",
            )

    def get_page(self):
        """Carga la página de identificación con Playwright headless (anti-detección)."""
        proxy_config = self._get_playwright_proxy()
        timeout_ms = 60000 if proxy_config else 20000
        user_agent = self.session.headers.get('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
        try:
            if proxy_config:
                self._log("Usando proxy (Playwright)")
            self._log("⏳ Cargando página con Playwright (headless)...")
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    ignore_default_args=['--enable-automation'],
                    args=['--disable-blink-features=AutomationControlled'],
                )
                context_kw = {
                    "locale": "es-CO",
                    "viewport": {"width": 1920, "height": 1080},
                    "user_agent": user_agent,
                }
                if proxy_config:
                    context_kw["proxy"] = proxy_config
                context = browser.new_context(**context_kw)
                Stealth().apply_stealth_sync(context)
                page = context.new_page()

                soup, nav_error = self._navigate_and_get_soup(page, timeout_ms)
                if not soup:
                    if proxy_config:
                        status = 403 if nav_error and ('403' in nav_error or 'restricted' in nav_error.lower()) else None
                        self._log_proxy_troubleshoot(response_status=status)
                    return None, None

                cookies = context.cookies()
                browser.close()

            self._apply_playwright_cookies_to_session(cookies)
            self._log("✓ Página cargada exitosamente (Playwright)")
            return soup, None

        except Exception as e:
            self._log(f"✗ Error al cargar página con Playwright: {e}", 'error')
            return None, None
        
    def get_sitekey(self, soup):
        try:
            recaptcha_div = soup.find('div', {'class': 'g-recaptcha'})
            if recaptcha_div and recaptcha_div.get('data-sitekey'):
                return recaptcha_div['data-sitekey']

            element = soup.find(attrs={'data-sitekey': True})
            if element:
                return element['data-sitekey']

            # reCAPTCHA v3: sitekey en script src con render= (ej. api.js?render=SITEKEY)
            recaptcha_script = soup.find('script', id='google-recaptcha-v3')
            if recaptcha_script and recaptcha_script.get('src'):
                match = re.search(r'render=([^&"\'\s]+)', recaptcha_script['src'])
                if match:
                    return match.group(1)

            html_text = str(soup)
            match = re.search(r'data-sitekey=["\']([^"\']+)["\']', html_text)
            if match:
                return match.group(1)

            match = re.search(r'render=([^&"\'\s]+)', html_text)
            if match:
                return match.group(1)

            match = re.search(r'recaptcha.*?k=([^&"\']+)', html_text)
            if match:
                return match.group(1)

        except Exception as e:
            self._log(f"⚠ Error al obtener sitekey: {e}", 'warning')

        return None
    
    def solve_captcha(self, sitekey):
        try:
            self._log("⏳ Resolviendo captcha con Two Captcha...")
            self._log("   Esto puede tomar entre 30-60 segundos...")
            
            result = self.solver.recaptcha(
                sitekey=sitekey,
                url=self.url
            )
            
            self._log("✓ Captcha resuelto exitosamente")
            return result['code']
            
        except Exception as e:
            error_msg = str(e).lower()
            
            if any(keyword in error_msg for keyword in ['balance', 'insufficient', 'funds', 'saldo', 'sin saldo', 'no funds', 'low balance']):
                self._log("✗ Error: El servicio 2Captcha no tiene saldo suficiente", 'error')
                return {
                    'error': 'insufficient_balance',
                    'message': 'El servicio 2Captcha no tiene saldo suficiente para resolver el captcha'
                }
            
            self._log(f"✗ Error al resolver captcha: {e}", 'error')
            return {
                'error': 'captcha_error',
                'message': f'Error al resolver captcha: {str(e)}'
            }
    
    def get_form_token(self, soup):
        try:
            token_input = soup.find('input', {'name': 'token'})
            if token_input and token_input.get('value'):
                self._log(f"✓ Token encontrado (method 1): {token_input['value'][:20]}...")
                return token_input['value']
            
            csrf_names = ['csrf_token', 'csrf', '_token', 'authenticity_token', '_csrf']
            for name in csrf_names:
                token_input = soup.find('input', {'name': name})
                if token_input and token_input.get('value'):
                    self._log(f"✓ Token encontrado (method 2, {name}): {token_input['value'][:20]}...")
                    return token_input['value']
            
            form = soup.find('form')
            if form:
                hidden_inputs = form.find_all('input', {'type': 'hidden'})
                for hidden in hidden_inputs:
                    value = hidden.get('value', '')
                    name = hidden.get('name', '')
                    if value and len(value) > 10 and name.lower() in ['token', 'csrf', '_token']:
                        self._log(f"✓ Token encontrado (method 3, {name}): {value[:20]}...")
                        return value
            
            meta_token = soup.find('meta', {'name': 'csrf-token'})
            if meta_token and meta_token.get('content'):
                self._log(f"✓ Token encontrado (method 4, meta): {meta_token['content'][:20]}...")
                return meta_token['content']
            
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string:
                    match = re.search(r'token\s*[=:]\s*["\']([^"\']{20,})["\']', script.string)
                    if match:
                        token = match.group(1)
                        self._log(f"✓ Token encontrado (method 5, JS): {token[:20]}...")
                        return token
            
            self._log("⚠ No se encontró token en el formulario", 'warning')
            return ""
            
        except Exception as e:
            self._log(f"⚠ Error al obtener token: {e}", 'warning')
            return ""
    
    def get_election_options(self, soup):
        """Obtiene opciones de elección desde la página. Valores son códigos (ej. 'congreso')."""
        opciones = {}
        try:
            for name in ('tipo', 'election_code', 'eleccion'):
                select = soup.find('select', {'name': name})
                if select:
                    for option in select.find_all('option'):
                        value = option.get('value', '').strip()
                        text = option.get_text(strip=True)
                        if value and text:
                            opciones[value] = text
                    break
        except Exception as e:
            self._log(f"⚠ Error al obtener opciones: {e}", 'warning')
        
        return opciones
    
    def _resolve_election_code(self, election_id, opciones):
        """Mapea election_id a election_code (string para la API)."""
        if election_id != -1 and election_id is not None:
            key = str(election_id)
            if key in opciones:
                return key
            return key
        if opciones:
            return list(opciones.keys())[0]
        return DEFAULT_ELECTION_CODE
    
    def query(self, id_number, election_id=-1):
        proxy_config = self._get_playwright_proxy()
        timeout_ms = 60000 if proxy_config else 20000
        user_agent = self.session.headers.get('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
        try:
            self._log(f"\n{'='*60}")
            self._log(f"Consultando lugar de votación para cédula: {id_number}")
            self._log(f"{'='*60}\n")

            if proxy_config:
                self._log("Usando proxy (Playwright)")
            self._log("⏳ Cargando página con Playwright (headless)...")
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    ignore_default_args=['--enable-automation'],
                    args=['--disable-blink-features=AutomationControlled'],
                )
                context_kw = {
                    "locale": "es-CO",
                    "viewport": {"width": 1920, "height": 1080},
                    "user_agent": user_agent,
                }
                if proxy_config:
                    context_kw["proxy"] = proxy_config
                context = browser.new_context(**context_kw)
                Stealth().apply_stealth_sync(context)
                page = context.new_page()

                soup, nav_error = self._navigate_and_get_soup(page, timeout_ms)
                if not soup:
                    if proxy_config:
                        status = 403 if nav_error and ('403' in nav_error or 'restricted' in nav_error.lower()) else None
                        self._log_proxy_troubleshoot(response_status=status)
                    return None

                self._log("✓ Página cargada exitosamente (Playwright)")

                self._log("⏳ Obteniendo opciones de elección...")
                opciones = self.get_election_options(soup)
                election_code = self._resolve_election_code(election_id, opciones)
                if opciones:
                    self._log(f"✓ Encontradas {len(opciones)} opciones de elección")
                    self._log(f"   Usando election_code: {election_code} ({opciones.get(election_code, 'por defecto')})")
                else:
                    self._log(f"   Usando election_code por defecto: {election_code}")

                self._log("⏳ Detectando captcha...")
                sitekey = self.get_sitekey(soup) or DEFAULT_SITEKEY
                if not sitekey:
                    self._log("✗ No se puede continuar sin sitekey", 'error')
                    return {'exito': False, 'error': 'No se pudo detectar el captcha en la página'}
                self._log(f"✓ Sitekey: {sitekey[:20]}...")

                captcha_result = self.solve_captcha(sitekey)
                if isinstance(captcha_result, dict):
                    if captcha_result.get('error') == 'insufficient_balance':
                        return {
                            'exito': False,
                            'error': captcha_result.get('message', 'El servicio 2Captcha no tiene saldo suficiente')
                        }
                    if captcha_result.get('error'):
                        return {
                            'exito': False,
                            'error': captcha_result.get('message', 'Error al resolver el captcha')
                        }

                token_captcha = captcha_result if isinstance(captcha_result, str) else None
                if not token_captcha:
                    return {'exito': False, 'error': 'No se pudo resolver el captcha'}

                self._log("⏳ Enviando consulta a la API Infovotantes (desde el navegador)...")
                self._log(f"   identification={id_number}, election_code={election_code}")

                payload = {
                    "identification": str(id_number),
                    "identification_type": "CC",
                    "election_code": election_code,
                    "platform": "web",
                    "module": "polling_place"
                }

                fetch_result = page.evaluate(
                    """async (args) => {
                        const r = await fetch(args.apiUrl, {
                            method: 'POST',
                            headers: {
                                'Authorization': 'Bearer ' + args.token,
                                'Content-Type': 'application/json',
                                'Accept': 'application/json, text/plain, */*'
                            },
                            body: JSON.stringify(args.payload)
                        });
                        const body = await r.text();
                        return JSON.stringify({ status: r.status, body: body });
                    }""",
                    {"apiUrl": self.api_url, "token": token_captcha, "payload": payload}
                )

                browser.close()

            try:
                result = json.loads(fetch_result)
            except (json.JSONDecodeError, TypeError):
                self._log("✗ No se pudo interpretar la respuesta del fetch", 'error')
                return {'exito': False, 'error': f'Error al llamar a la API desde el navegador: {str(fetch_result)[:300]}'}

            status = result.get("status", 0)
            response_text = result.get("body", "")

            if status >= 400:
                self._log(f"✗ API respondió con status {status}", 'error')
                return {'exito': False, 'error': f'La API respondió con error {status}: {response_text[:200]}'}

            self._log("✓ Respuesta recibida")
            self._log("⏳ Extrayendo información...")
            return self.extract_information(response_text)

        except Exception as e:
            self._log(f"\n✗ Error durante la consulta: {e}", 'error')
            import traceback
            self._log(traceback.format_exc(), 'error')
            return {'exito': False, 'error': f'Error inesperado: {str(e)}'}
    
    def extract_information(self, raw_response):
        try:
            try:
                data = json.loads(raw_response)
            except (json.JSONDecodeError, ValueError):
                data = None
            
            if isinstance(data, dict):
                # Respuesta de la API Infovotantes (status/status_code/data o exito/error)
                resultado = self._extract_from_api_json(data)
                if resultado is not None:
                    return resultado
                # JSON antiguo con HTML embebido (compatibilidad)
                if data.get('success') and data.get('data', {}).get('message'):
                    self._log("✓ Respuesta JSON con HTML embebido, extrayendo...")
                    return self._extract_from_html(data['data']['message'])
                if data.get('success') is False:
                    return {
                        'exito': False,
                        'error': data.get('message', 'Error desconocido')
                    }
            
            return self._extract_from_html(raw_response)
            
        except Exception as e:
            self._log(f"✗ Error al extraer información: {e}", 'error')
            import traceback
            self._log(traceback.format_exc(), 'error')
            return {'exito': False, 'error': f'Error al procesar resultados: {str(e)}'}
    
    def _extract_from_api_json(self, data):
        """
        Interpreta la respuesta JSON de la API get-information (Infovotantes).
        Formatos: 1) puesto encontrado (status/data.polling_place), 2) error (exito False/404),
        3) novedad (data.novelty).
        """
        # Caso error: respuesta con exito False (ej. 404 Not Found)
        if data.get('exito') is False:
            return {
                'exito': False,
                'error': data.get('error', 'Error desconocido al consultar lugar de votación')
            }
        
        # Formato nuevo API: status + status_code + data
        if 'status' in data and 'data' in data:
            inner = data.get('data')
            if not isinstance(inner, dict):
                return None
            status_ok = data.get('status') is True and data.get('status_code') == 0
            
            # Novedad: data con lista 'novelty'
            novelty_list = inner.get('novelty') or inner.get('novedad')
            if isinstance(novelty_list, list) and len(novelty_list) > 0:
                first = novelty_list[0]
                resultado = {'exito': True, 'datos': {}, 'tipo': 'novedad'}
                voter = inner.get('voter') or {}
                if isinstance(voter, dict) and voter.get('identification'):
                    resultado['datos']['nuip'] = str(voter.get('identification', '')).strip()
                # Texto de la novedad: name + description_line_1
                parts = []
                if first.get('name'):
                    parts.append(str(first['name']).strip())
                if first.get('description_line_1'):
                    parts.append(str(first['description_line_1']).strip())
                resultado['datos']['novedad'] = ' '.join(parts) if parts else (first.get('procedure') or 'Novedad registrada')
                if first.get('resolution'):
                    resultado['datos']['resolucion'] = str(first['resolution']).strip()
                if first.get('date'):
                    resultado['datos']['fecha_novedad'] = str(first['date']).strip()
                self._log(f"✓ Novedad extraída de API JSON")
                return resultado
            
            # Puesto de votación: data con polling_place y place_address
            polling = inner.get('polling_place') or inner.get('pollingPlace')
            if isinstance(polling, dict) and status_ok:
                resultado = {'exito': True, 'datos': {}, 'tipo': 'lugar_votacion'}
                voter = inner.get('voter') or {}
                if isinstance(voter, dict) and voter.get('identification'):
                    resultado['datos']['nuip'] = str(voter.get('identification', '')).strip()
                resultado['datos']['puesto'] = str((polling.get('stand') or polling.get('stand_code')) or '').strip()
                resultado['datos']['mesa'] = str(polling.get('table', '')).strip() if polling.get('table') is not None else ''
                addr = polling.get('place_address') or {}
                if isinstance(addr, dict):
                    if addr.get('state'):
                        resultado['datos']['departamento'] = str(addr['state']).strip()
                    if addr.get('town'):
                        resultado['datos']['municipio'] = str(addr['town']).strip()
                    if addr.get('address'):
                        resultado['datos']['direccion'] = str(addr['address']).strip()
                if resultado['datos'].get('puesto') or resultado['datos'].get('departamento') or resultado['datos'].get('municipio'):
                    self._log(f"✓ Datos de puesto extraídos de API JSON: {len(resultado['datos'])} campos")
                    return resultado
            
            # data sin polling_place ni novelty (ej. no en censo pero sin lista novelty)
            if status_ok and inner.get('is_in_census') is False and not novelty_list:
                return {
                    'exito': False,
                    'error': 'El documento no se encuentra en el censo electoral para esta elección.'
                }
            return None
        
        # Formato legacy: success/data
        if data.get('success') is False:
            return {
                'exito': False,
                'error': data.get('message', data.get('error', 'Error desconocido'))
            }
        inner = data.get('data') if isinstance(data.get('data'), dict) else data
        if not inner:
            return None
        resultado = {'exito': True, 'datos': {}, 'tipo': 'lugar_votacion'}
        for api_key, our_key in [
            ('identification', 'nuip'), ('nuip', 'nuip'), ('department', 'departamento'),
            ('state', 'departamento'), ('city', 'municipio'), ('town', 'municipio'),
            ('address', 'direccion'), ('table', 'mesa'), ('stand', 'puesto'),
            ('resolution', 'resolucion'), ('novedad', 'novedad'),
        ]:
            val = inner.get(api_key)
            if val is not None and str(val).strip():
                resultado['datos'][our_key] = str(val).strip()
        for key in ('polling_place', 'pollingPlace'):
            sub = inner.get(key)
            if isinstance(sub, dict):
                addr = sub.get('place_address') or {}
                if addr.get('state') and 'departamento' not in resultado['datos']:
                    resultado['datos']['departamento'] = str(addr['state']).strip()
                if addr.get('town') and 'municipio' not in resultado['datos']:
                    resultado['datos']['municipio'] = str(addr['town']).strip()
                if addr.get('address') and 'direccion' not in resultado['datos']:
                    resultado['datos']['direccion'] = str(addr['address']).strip()
                if sub.get('stand') and 'puesto' not in resultado['datos']:
                    resultado['datos']['puesto'] = str(sub['stand']).strip()
                if sub.get('table') is not None and 'mesa' not in resultado['datos']:
                    resultado['datos']['mesa'] = str(sub['table']).strip()
                break
        if resultado['datos'].get('novedad'):
            resultado['tipo'] = 'novedad'
        if not resultado['datos']:
            return None
        self._log(f"✓ Datos extraídos de API JSON: {len(resultado['datos'])} campos")
        return resultado
    
    def _extract_from_html(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        
        error_selectors = [
            '.error', '.alert-danger', '.mensaje-error',
            '.alert.alert-danger', '#error', '.errorMsg'
        ]
        
        for selector in error_selectors:
            error_elem = soup.select_one(selector)
            if error_elem:
                error_text = error_elem.get_text(strip=True)
                if error_text and len(error_text) > 5:
                    return {
                        'exito': False,
                        'error': error_text
                    }
        
        resultado = {
            'exito': True,
            'datos': {},
            'tipo': None
        }
        
        tabla = soup.find('table', {'id': 'consulta'}) or soup.find('table', {'class': ['table', 'table-bordered']})
        
        if tabla:
            print("✓ Tabla de resultados encontrada")
            
            headers = []
            thead = tabla.find('thead')
            if thead:
                ths = thead.find_all('th')
                headers = [th.get_text(strip=True).lower() for th in ths]
                print(f"   Headers: {headers}")
            
            es_novedad = any('novedad' in h for h in headers)
            
            tbody = tabla.find('tbody')
            if tbody:
                primera_fila = tbody.find('tr')
                if primera_fila:
                    celdas = primera_fila.find_all('td')
                    
                    if len(celdas) == 1 and celdas[0].get('colspan'):
                        filas = tbody.find_all('tr')
                        if len(filas) > 1:
                            primera_fila = filas[0]
                            celdas = primera_fila.find_all('td')
                    
                    self._log(f"   Procesando {len(celdas)} celdas...")
                    for i, celda in enumerate(celdas):
                        campo = celda.get('data-th', '').strip()
                        if not campo and i < len(headers):
                            campo = headers[i]
                        
                        valor = celda.get_text(strip=True)
                        
                        if campo and valor:
                            self._log(f"     [{i}] {campo} = {valor[:50]}")
                        
                        if campo and valor:
                            campo_lower = campo.lower().replace('ó', 'o').replace('í', 'i')
                            campo_normalizado = re.sub(r'[^a-z0-9\s]', '', campo_lower).strip()
                            
                            if ('fecha' in campo_normalizado and 'novedad' in campo_normalizado) or 'fecha novedad' in campo_lower:
                                resultado['datos']['fecha_novedad'] = valor
                            elif 'nuip' in campo_normalizado:
                                resultado['datos']['nuip'] = valor
                            elif 'departamento' in campo_normalizado:
                                resultado['datos']['departamento'] = valor
                            elif 'municipio' in campo_normalizado:
                                resultado['datos']['municipio'] = valor
                            elif 'puesto' in campo_normalizado:
                                resultado['datos']['puesto'] = valor
                            elif 'direccion' in campo_normalizado or 'direcci' in campo_normalizado:
                                resultado['datos']['direccion'] = valor
                            elif 'mesa' in campo_normalizado:
                                resultado['datos']['mesa'] = valor
                            elif 'novedad' in campo_normalizado:
                                resultado['datos']['novedad'] = valor
                                resultado['tipo'] = 'novedad'
                            elif 'resolucion' in campo_normalizado or 'resoluci' in campo_normalizado:
                                resultado['datos']['resolucion'] = valor
                            elif 'fecha' in campo_normalizado:
                                if not resultado['datos'].get('fecha_novedad'):
                                    resultado['datos']['fecha_novedad'] = valor
                            else:
                                resultado['datos'][campo_lower] = valor
                    
                    if resultado['tipo'] == 'novedad' or 'novedad' in resultado['datos']:
                        resultado['tipo'] = 'novedad'
                        print(f"⚠ Novedad detectada:")
                        if 'nuip' in resultado['datos']:
                            print(f"   • NUIP: {resultado['datos']['nuip']}")
                        if 'novedad' in resultado['datos']:
                            print(f"   • NOVEDAD: {resultado['datos']['novedad']}")
                        if 'resolucion' in resultado['datos']:
                            print(f"   • RESOLUCIÓN: {resultado['datos']['resolucion']}")
                        if 'fecha_novedad' in resultado['datos']:
                            print(f"   • FECHA: {resultado['datos']['fecha_novedad']}")
                        return resultado
                    else:
                        campos_esperados = ['nuip', 'departamento', 'municipio', 'puesto']
                        campos_encontrados = [c for c in campos_esperados if c in resultado['datos']]
                        
                        if campos_encontrados:
                            resultado['tipo'] = 'lugar_votacion'
                            print(f"✓ Datos extraídos exitosamente:")
                            for campo in ['nuip', 'departamento', 'municipio', 'puesto', 'direccion', 'mesa']:
                                if campo in resultado['datos']:
                                    print(f"   • {campo.upper()}: {resultado['datos'][campo]}")
                            return resultado
        
        texto_completo = soup.get_text(separator='\n', strip=True)
        
        patrones = {
            'nuip': r'NUIP[:\s]+(\d+)',
            'departamento': r'DEPARTAMENTO[:\s]+([A-ZÁÉÍÓÚÑ\s]+)',
            'municipio': r'MUNICIPIO[:\s]+([A-ZÁÉÍÓÚÑ\s]+)',
            'puesto': r'PUESTO[:\s]+([A-ZÁÉÍÓÚÑ0-9\s\-\.]+)',
            'direccion': r'DIRECCI[OÓ]N[:\s]+([A-ZÁÉÍÓÚÑ0-9\s\-\.#]+)',
            'mesa': r'MESA[:\s]+(\d+)'
        }
        
        for campo, patron in patrones.items():
            match = re.search(patron, texto_completo, re.IGNORECASE)
            if match:
                resultado['datos'][campo] = match.group(1).strip()
        
        if resultado['datos']:
            self._log(f"✓ Información extraída con patrones: {len(resultado['datos'])} campos")
            return resultado
        
        texto_lower = texto_completo.lower()
        if any(msg in texto_lower for msg in [
            'no se encontr', 'no existe', 'no registra',
            'cedula no', 'cédula no', 'dato no válido', 'nuip no válido'
        ]):
            return {
                'exito': False,
                'error': 'No se encontró información para esta cédula'
            }
        
        if not resultado['datos']:
            return {
                'exito': False,
                'error': 'No se pudo extraer información de la respuesta',
                'contenido_raw': texto_completo[:500]
            }
        
        return resultado
