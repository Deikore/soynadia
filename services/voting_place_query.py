#!/usr/bin/env python3

import os
import time
import re
import requests
from bs4 import BeautifulSoup
from twocaptcha import TwoCaptcha
from dotenv import load_dotenv


class VotingPlaceQuery:
    
    def __init__(self, api_key, logger=None):
        self.api_key = api_key
        self.url = "https://wsp.registraduria.gov.co/censo/consultar/"
        self.solver = TwoCaptcha(api_key)
        self.session = requests.Session()
        self.logger = logger
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
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
        
    def get_page(self):
        try:
            self._log("⏳ Cargando página...")
            response = self.session.get(self.url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            self._log("✓ Página cargada exitosamente")
            return soup, response
            
        except Exception as e:
            self._log(f"✗ Error al cargar página: {e}", 'error')
            return None, None
        
    def get_sitekey(self, soup):
        try:
            recaptcha_div = soup.find('div', {'class': 'g-recaptcha'})
            if recaptcha_div and recaptcha_div.get('data-sitekey'):
                return recaptcha_div['data-sitekey']
            
            element = soup.find(attrs={'data-sitekey': True})
            if element:
                return element['data-sitekey']
            
            html_text = str(soup)
            match = re.search(r'data-sitekey=["\']([^"\']+)["\']', html_text)
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
        opciones = {}
        try:
            select = soup.find('select', {'name': 'tipo'})
            if select:
                for option in select.find_all('option'):
                    value = option.get('value', '')
                    text = option.get_text(strip=True)
                    if value and text:
                        opciones[value] = text
        except Exception as e:
            self._log(f"⚠ Error al obtener opciones: {e}", 'warning')
        
        return opciones
    
    def query(self, id_number, election_id=-1):
        try:
            self._log(f"\n{'='*60}")
            self._log(f"Consultando lugar de votación para cédula: {id_number}")
            self._log(f"{'='*60}\n")
            
            soup, response = self.get_page()
            if not soup:
                return None
            
            self._log("⏳ Extrayendo token del formulario...")
            token_form = self.get_form_token(soup)
            
            self._log("⏳ Obteniendo opciones de elección...")
            opciones = self.get_election_options(soup)
            
            if not opciones:
                self._log("⚠ No se encontraron opciones de elección", 'warning')
                if election_id == -1:
                    election_id = "-1"
            else:
                self._log(f"✓ Encontradas {len(opciones)} opciones de elección")
                if election_id == -1:
                    election_id = list(opciones.keys())[0] if opciones else "-1"
                    self._log(f"   Usando: {opciones.get(election_id, 'Opción por defecto')}")
            
            self._log("⏳ Detectando captcha...")
            sitekey = self.get_sitekey(soup)
            
            if not sitekey:
                self._log("✗ No se pudo detectar el sitekey del captcha", 'error')
                self._log("⚠ Intentando con sitekey genérico...", 'warning')
                sitekey = None
            else:
                self._log(f"✓ Sitekey detectado: {sitekey[:20]}...")
            
            if not sitekey:
                self._log("✗ No se puede continuar sin sitekey", 'error')
                return {
                    'exito': False,
                    'error': 'No se pudo detectar el captcha en la página'
                }
            
            captcha_result = self.solve_captcha(sitekey)
            
            if isinstance(captcha_result, dict):
                if captcha_result.get('error') == 'insufficient_balance':
                    return {
                        'exito': False,
                        'error': captcha_result.get('message', 'El servicio 2Captcha no tiene saldo suficiente')
                    }
                elif captcha_result.get('error'):
                    return {
                        'exito': False,
                        'error': captcha_result.get('message', 'Error al resolver el captcha')
                    }
            
            token_captcha = captcha_result if isinstance(captcha_result, str) else None
            
            if not token_captcha:
                return {
                    'exito': False,
                    'error': 'No se pudo resolver el captcha'
                }
            
            self._log("⏳ Preparando formulario...")
            form_data = {
                'nuip': id_number,
                'tipo': str(election_id),
                'g-recaptcha-response': token_captcha
            }
            
            if token_form:
                form_data['token'] = token_form
                self._log("✓ Token agregado al formulario")
            
            self._log("⏳ Enviando consulta...")
            self._log(f"   Datos: nuip={id_number}, tipo={election_id}")
            
            headers_post = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json, text/html, */*',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            response = self.session.post(
                self.url,
                data=form_data,
                headers=headers_post,
                timeout=30,
                allow_redirects=True
            )
            
            response.raise_for_status()
            self._log(f"✓ Respuesta recibida (status: {response.status_code})")
            self._log(f"   Content-Type: {response.headers.get('Content-Type', 'N/A')}")
            
            self._log("⏳ Extrayendo información...")
            resultado = self.extract_information(response.text)
            
            return resultado
            
        except requests.exceptions.RequestException as e:
            self._log(f"\n✗ Error de conexión: {e}", 'error')
            return {
                'exito': False,
                'error': f'Error de conexión: {str(e)}'
            }
        except Exception as e:
            self._log(f"\n✗ Error durante la consulta: {e}", 'error')
            import traceback
            self._log(traceback.format_exc(), 'error')
            return {
                'exito': False,
                'error': f'Error inesperado: {str(e)}'
            }
    
    def extract_information(self, html):
        try:
            import json
            try:
                data = json.loads(html)
                if isinstance(data, dict):
                    if data.get('success') is False:
                        mensaje = data.get('message', 'Error desconocido')
                        return {
                            'exito': False,
                            'error': mensaje
                        }
                    
                    if data.get('success') and data.get('data', {}).get('message'):
                        html_embebido = data['data']['message']
                        print("✓ Respuesta JSON detectada, extrayendo HTML embebido...")
                        return self._extract_from_html(html_embebido)
            except (json.JSONDecodeError, ValueError):
                pass
            
            return self._extract_from_html(html)
            
        except Exception as e:
            self._log(f"✗ Error al extraer información: {e}", 'error')
            import traceback
            self._log(traceback.format_exc(), 'error')
            return {
                'exito': False,
                'error': f'Error al procesar resultados: {str(e)}'
            }
    
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
