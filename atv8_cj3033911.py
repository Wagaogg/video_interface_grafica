# main.py
import sys
import os
import re
import sqlite3
import subprocess
import platform
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QGridLayout, QLabel, QLineEdit, 
                              QPushButton, QComboBox, QMessageBox, QGroupBox,
                              QTableWidget, QTableWidgetItem, QHeaderView,
                              QTabWidget, QDialog, QFrame, QScrollArea,
                              QFileDialog)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
import requests

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                Paragraph, Spacer)


# ============================================================
# MÓDULO DE VALIDAÇÕES
# ============================================================

class Validador:
    """Classe responsável por validações de dados"""
    
    @staticmethod
    def validar_cpf(cpf):
        if not cpf:
            return False, "CPF é obrigatório"
        
        cpf = re.sub(r'[^0-9]', '', cpf)
        
        if len(cpf) != 11:
            return False, "CPF deve ter 11 dígitos. Formato: 000.000.000-00"
        
        if len(set(cpf)) == 1:
            return False, "CPF inválido"
        
        soma = 0
        for i in range(9):
            soma += int(cpf[i]) * (10 - i)
        resto = 11 - (soma % 11)
        digito1 = 0 if resto >= 10 else resto
        
        soma = 0
        for i in range(10):
            soma += int(cpf[i]) * (11 - i)
        resto = 11 - (soma % 11)
        digito2 = 0 if resto >= 10 else resto
        
        if int(cpf[9]) == digito1 and int(cpf[10]) == digito2:
            return True, ""
        return False, "CPF inválido. Verifique os números digitados."
    
    @staticmethod
    def validar_cnpj(cnpj):
        if not cnpj:
            return False, "CNPJ é obrigatório"
        
        cnpj = re.sub(r'[^0-9]', '', cnpj)
        
        if len(cnpj) != 14:
            return False, "CNPJ deve ter 14 dígitos. Formato: 00.000.000/0000-00"
        
        if len(set(cnpj)) == 1:
            return False, "CNPJ inválido"
        
        soma = 0
        multiplicadores = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        for i in range(12):
            soma += int(cnpj[i]) * multiplicadores[i]
        resto = soma % 11
        digito1 = 0 if resto < 2 else 11 - resto
        
        soma = 0
        multiplicadores = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        for i in range(13):
            soma += int(cnpj[i]) * multiplicadores[i]
        resto = soma % 11
        digito2 = 0 if resto < 2 else 11 - resto
        
        if int(cnpj[12]) == digito1 and int(cnpj[13]) == digito2:
            return True, ""
        return False, "CNPJ inválido. Verifique os números digitados."
    
    @staticmethod
    def validar_email(email):
        if not email or not email.strip():
            return False, "E-mail é obrigatório"
        
        email = email.strip()
        padrao = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if re.match(padrao, email):
            return True, ""
        return False, "E-mail inválido. Exemplo: usuario@dominio.com"
    
    @staticmethod
    def validar_telefone(telefone):
        if not telefone:
            return False, "Celular é obrigatório"
        telefone = re.sub(r'[^0-9]', '', telefone)
        if len(telefone) >= 10 and len(telefone) <= 11:
            return True, ""
        return False, "Celular inválido. Use (00) 00000-0000 ou (00) 0000-0000"
    
    @staticmethod
    def validar_cep(cep):
        if not cep:
            return False, "CEP é obrigatório"
        cep = re.sub(r'[^0-9]', '', cep)
        if len(cep) == 8:
            return True, ""
        return False, "CEP inválido. Formato esperado: 00000-000"
    
    @staticmethod
    def validar_campo_obrigatorio(valor, nome_campo):
        if not valor or not valor.strip():
            return False, f"{nome_campo} é obrigatório"
        return True, ""


# ============================================================
# THREAD PARA CONSULTAR CEP
# ============================================================

class ConsultaCEPThread(QThread):
    resultado = Signal(dict)
    erro = Signal(str)
    
    def __init__(self, cep):
        super().__init__()
        self.cep = cep
    
    def run(self):
        try:
            cep = re.sub(r'[^0-9]', '', self.cep)
            url = f"https://viacep.com.br/ws/{cep}/json/"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            
            dados = response.json()
            
            if 'erro' in dados:
                self.erro.emit("CEP não encontrado.")
                return
            
            endereco = {
                'logradouro': dados.get('logradouro', ''),
                'bairro': dados.get('bairro', ''),
                'cidade': dados.get('localidade', ''),
                'estado': dados.get('uf', ''),
                'complemento': dados.get('complemento', '')
            }
            
            self.resultado.emit(endereco)
            
        except requests.exceptions.Timeout:
            self.erro.emit("Tempo limite excedido. Verifique sua conexão.")
        except requests.exceptions.ConnectionError:
            self.erro.emit("Erro de conexão. Verifique sua rede.")
        except requests.exceptions.RequestException:
            self.erro.emit("Erro ao consultar o CEP.")
        except Exception:
            self.erro.emit("Erro inesperado.")


# ============================================================
# MÓDULO DE BANCO DE DADOS
# ============================================================

class Database:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self.inicializar_banco()
    
    def inicializar_banco(self):
        try:
            os.makedirs('data', exist_ok=True)
            self.conn = sqlite3.connect('data/cadastros.db')
            self.cursor = self.conn.cursor()
            
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS pessoas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome_completo TEXT NOT NULL,
                    tipo_documento TEXT NOT NULL,
                    documento TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL,
                    celular TEXT NOT NULL,
                    cep TEXT NOT NULL,
                    logradouro TEXT,
                    numero TEXT,
                    complemento TEXT,
                    bairro TEXT,
                    cidade TEXT,
                    estado TEXT,
                    data_cadastro TEXT NOT NULL,
                    data_atualizacao TEXT
                )
            ''')
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Erro ao inicializar banco de dados: {e}")
    
    def inserir_pessoa(self, dados):
        try:
            documento = re.sub(r'[^0-9]', '', dados['documento'])
            self.cursor.execute('''
                INSERT INTO pessoas (
                    nome_completo, tipo_documento, documento, email, celular,
                    cep, logradouro, numero, complemento, bairro, cidade, estado,
                    data_cadastro
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                dados['nome_completo'], dados['tipo_documento'], documento,
                dados['email'], dados['celular'], dados['cep'], dados['logradouro'],
                dados['numero'], dados['complemento'], dados['bairro'],
                dados['cidade'], dados['estado'], datetime.now().isoformat()
            ))
            self.conn.commit()
            return True, "Cadastro realizado com sucesso!"
        except sqlite3.IntegrityError:
            return False, "Este documento já está cadastrado."
        except sqlite3.Error as e:
            return False, f"Erro ao cadastrar: {str(e)}"
    
    def listar_pessoas(self):
        try:
            self.cursor.execute('''
                SELECT id, nome_completo, documento, email, celular, cidade, estado
                FROM pessoas ORDER BY nome_completo
            ''')
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Erro ao listar pessoas: {e}")
            return []
    
    def listar_todas_pessoas(self):
        """Retorna todos os campos de todos os cadastros, ordenados por nome."""
        try:
            self.cursor.execute('''
                SELECT id, nome_completo, tipo_documento, documento, email,
                       celular, cep, logradouro, numero, complemento,
                       bairro, cidade, estado, data_cadastro
                FROM pessoas ORDER BY nome_completo
            ''')
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Erro ao listar pessoas: {e}")
            return []
    
    def buscar_pessoa(self, id_pessoa):
        try:
            self.cursor.execute('SELECT * FROM pessoas WHERE id = ?', (id_pessoa,))
            return self.cursor.fetchone()
        except sqlite3.Error as e:
            print(f"Erro ao buscar pessoa: {e}")
            return None
    
    def atualizar_pessoa(self, id_pessoa, dados):
        try:
            documento = re.sub(r'[^0-9]', '', dados['documento'])
            self.cursor.execute('''
                UPDATE pessoas SET
                    nome_completo = ?, tipo_documento = ?, documento = ?,
                    email = ?, celular = ?, cep = ?, logradouro = ?,
                    numero = ?, complemento = ?, bairro = ?, cidade = ?,
                    estado = ?, data_atualizacao = ?
                WHERE id = ?
            ''', (
                dados['nome_completo'], dados['tipo_documento'], documento,
                dados['email'], dados['celular'], dados['cep'], dados['logradouro'],
                dados['numero'], dados['complemento'], dados['bairro'],
                dados['cidade'], dados['estado'], datetime.now().isoformat(),
                id_pessoa
            ))
            self.conn.commit()
            return True, "Dados atualizados com sucesso!"
        except sqlite3.IntegrityError:
            return False, "Este documento já está cadastrado para outra pessoa."
        except sqlite3.Error as e:
            return False, f"Erro ao atualizar: {str(e)}"
    
    def excluir_pessoa(self, id_pessoa):
        try:
            self.cursor.execute('DELETE FROM pessoas WHERE id = ?', (id_pessoa,))
            self.conn.commit()
            return True, "Registro excluído com sucesso!"
        except sqlite3.Error as e:
            return False, f"Erro ao excluir: {str(e)}"
    
    def fechar(self):
        if self.conn:
            self.conn.close()


# ============================================================
# DIÁLOGO DE DETALHES
# ============================================================

class DetalhesPessoaDialog(QDialog):
    def __init__(self, dados, parent=None):
        super().__init__(parent)
        self.dados = dados
        self.setWindowTitle("Detalhes do Cadastro")
        self.setMinimumSize(600, 500)
        self.setup_style()
        self.iniciar_interface()
        self.carregar_dados()
    
    def setup_style(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
            QLabel {
                color: #e0e0e0;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QPushButton {
                background-color: #3a3a3a;
                color: #e0e0e0;
                border: none;
                padding: 12px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
    
    def iniciar_interface(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
        header = QLabel("DETALHES DO CADASTRO")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            padding: 15px;
            background-color: #2c2c2c;
            color: #e0e0e0;
            border-radius: 6px;
        """)
        layout.addWidget(header)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        conteudo = QWidget()
        grid = QGridLayout(conteudo)
        grid.setSpacing(10)
        grid.setContentsMargins(20, 20, 20, 20)
        
        self.campos = {}
        campos_info = [
            ("ID:", "id"),
            ("Nome Completo:", "nome_completo"),
            ("Tipo Documento:", "tipo_documento"),
            ("Documento:", "documento"),
            ("E-mail:", "email"),
            ("Celular:", "celular"),
            ("CEP:", "cep"),
            ("Logradouro:", "logradouro"),
            ("Número:", "numero"),
            ("Complemento:", "complemento"),
            ("Bairro:", "bairro"),
            ("Cidade:", "cidade"),
            ("Estado:", "estado"),
            ("Data Cadastro:", "data_cadastro"),
            ("Data Atualização:", "data_atualizacao")
        ]
        
        for i, (label, campo) in enumerate(campos_info):
            lbl = QLabel(label)
            lbl.setStyleSheet("font-weight: bold; color: #a0a0a0;")
            valor = QLabel("")
            valor.setStyleSheet("""
                padding: 6px 12px;
                background-color: #2c2c2c;
                border-radius: 4px;
                border: 1px solid #3a3a3a;
                color: #e0e0e0;
            """)
            valor.setWordWrap(True)
            grid.addWidget(lbl, i, 0, Qt.AlignTop)
            grid.addWidget(valor, i, 1)
            self.campos[campo] = valor
        
        scroll.setWidget(conteudo)
        layout.addWidget(scroll)
        
        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(self.close)
        layout.addWidget(btn_fechar)
        
        self.setLayout(layout)
    
    def carregar_dados(self):
        if self.dados:
            campos = [
                'id', 'nome_completo', 'tipo_documento', 'documento',
                'email', 'celular', 'cep', 'logradouro', 'numero',
                'complemento', 'bairro', 'cidade', 'estado',
                'data_cadastro', 'data_atualizacao'
            ]
            for i, campo in enumerate(campos):
                if i < len(self.dados):
                    valor = str(self.dados[i]) if self.dados[i] else "Não informado"
                    if campo in self.campos:
                        self.campos[campo].setText(valor)


# ============================================================
# JANELA PRINCIPAL
# ============================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.pessoa_editando = None
        self.thread_consulta = None
        self.setup_style()
        self.iniciar_interface()
        self.carregar_lista()
    
    def setup_style(self):
        self.setWindowTitle("Sistema de Cadastro")
        self.setMinimumSize(1100, 750)
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1a1a1a;
            }
            QTabWidget::pane {
                background: #1e1e1e;
                border-radius: 6px;
                border: 1px solid #2c2c2c;
                padding: 15px;
            }
            QTabBar::tab {
                background: #2c2c2c;
                padding: 10px 25px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
                font-weight: 500;
                color: #a0a0a0;
                font-size: 13px;
            }
            QTabBar::tab:selected {
                background: #1e1e1e;
                border-bottom: 2px solid #3498db;
                color: #e0e0e0;
            }
            QTabBar::tab:hover:!selected {
                background: #3a3a3a;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #2c2c2c;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
                background: #1e1e1e;
                font-size: 13px;
                color: #e0e0e0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 4px 15px;
                background-color: #2c2c2c;
                color: #e0e0e0;
                border-radius: 4px;
            }
            QLabel {
                color: #c0c0c0;
                font-size: 12px;
            }
            QLineEdit, QComboBox {
                padding: 10px 12px;
                border: 1px solid #2c2c2c;
                border-radius: 4px;
                background: #2c2c2c;
                font-size: 13px;
                color: #f5f5f5;
                selection-background-color: #3498db;
                selection-color: white;
            }
            QComboBox QAbstractItemView {
                background-color: #2c2c2c;
                color: #f5f5f5;
                selection-background-color: #3498db;
                selection-color: white;
                border: 1px solid #3498db;
                outline: 0;
            }
            QLineEdit:focus, QComboBox:focus {
                border-color: #3498db;
                background: #2c2c2c;
            }
            QLineEdit:disabled {
                background: #1a1a1a;
                color: #7f8c8d;
            }
            QLineEdit::placeholder {
                color: #7f8c8d;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #7f8c8d;
                margin-right: 5px;
            }
            QPushButton {
                padding: 10px 25px;
                border: none;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
                color: #f5f5f5;
                min-height: 18px;
            }
            QPushButton:hover {
                opacity: 0.85;
            }
            QTableWidget {
                background: #1e1e1e;
                border-radius: 4px;
                border: 1px solid #2c2c2c;
                gridline-color: #2c2c2c;
            }
            QTableWidget::item {
                padding: 10px;
                color: #c0c0c0;
            }
            QTableWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QHeaderView::section {
                background: #2c2c2c;
                padding: 10px;
                border: none;
                border-bottom: 1px solid #2c2c2c;
                font-weight: bold;
                color: #a0a0a0;
                font-size: 12px;
            }
            QScrollBar:vertical {
                border: none;
                background: #1a1a1a;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #3a3a3a;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #4a4a4a;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
            QMessageBox {
                background-color: #1e1e1e;
            }
            QMessageBox QLabel {
                color: #e0e0e0;
            }
            QMessageBox QPushButton {
                background-color: #2c2c2c;
                color: #e0e0e0;
                padding: 8px 20px;
                border-radius: 4px;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: #3a3a3a;
            }
        """)
    
    def iniciar_interface(self):
        widget_central = QWidget()
        self.setCentralWidget(widget_central)
        
        header = QLabel("SISTEMA DE CADASTRO")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            padding: 18px;
            background-color: #2c2c2c;
            color: #e0e0e0;
            border-radius: 6px;
            letter-spacing: 2px;
        """)
        
        self.tabs = QTabWidget()
        self.tab_cadastro = QWidget()
        self.tab_lista = QWidget()
        self.tabs.addTab(self.tab_cadastro, "Cadastro")
        self.tabs.addTab(self.tab_lista, "Lista de Cadastros")
        
        layout_principal = QVBoxLayout(widget_central)
        layout_principal.setSpacing(15)
        layout_principal.addWidget(header)
        layout_principal.addWidget(self.tabs)
        
        self.configurar_aba_cadastro()
        self.configurar_aba_lista()
    
    def configurar_aba_cadastro(self):
        layout = QVBoxLayout(self.tab_cadastro)
        layout.setSpacing(15)
        
        grupo = QGroupBox("Dados Pessoais")
        grupo_layout = QGridLayout()
        grupo_layout.setVerticalSpacing(12)
        grupo_layout.setHorizontalSpacing(12)
        
        self.campos = {}
        
        # Nome
        grupo_layout.addWidget(QLabel("Nome Completo:*"), 0, 0)
        self.campos['nome'] = QLineEdit()
        self.campos['nome'].setPlaceholderText("Digite o nome completo")
        grupo_layout.addWidget(self.campos['nome'], 0, 1, 1, 3)
        
        # Tipo Documento e Documento
        grupo_layout.addWidget(QLabel("Tipo Documento:*"), 1, 0)
        self.campos['tipo_doc'] = QComboBox()
        self.campos['tipo_doc'].addItems(["CPF", "CNPJ"])
        self.campos['tipo_doc'].currentTextChanged.connect(self.atualizar_mascara_documento)
        grupo_layout.addWidget(self.campos['tipo_doc'], 1, 1)
        
        grupo_layout.addWidget(QLabel("Documento:*"), 1, 2)
        self.campos['documento'] = QLineEdit()
        self.campos['documento'].setPlaceholderText("000.000.000-00")
        self.campos['documento'].setMaxLength(14)
        self.campos['documento'].textChanged.connect(self.aplicar_mascara_documento)
        grupo_layout.addWidget(self.campos['documento'], 1, 3)
        
        # Email e Celular
        grupo_layout.addWidget(QLabel("E-mail:*"), 2, 0)
        self.campos['email'] = QLineEdit()
        self.campos['email'].setPlaceholderText("exemplo@dominio.com")
        grupo_layout.addWidget(self.campos['email'], 2, 1)
        
        grupo_layout.addWidget(QLabel("Celular:*"), 2, 2)
        self.campos['celular'] = QLineEdit()
        self.campos['celular'].setPlaceholderText("(00) 00000-0000")
        self.campos['celular'].textChanged.connect(self.aplicar_mascara_celular)
        grupo_layout.addWidget(self.campos['celular'], 2, 3)
        
        # CEP e Botão Consultar
        grupo_layout.addWidget(QLabel("CEP:*"), 3, 0)
        self.campos['cep'] = QLineEdit()
        self.campos['cep'].setPlaceholderText("00000-000")
        self.campos['cep'].textChanged.connect(self.aplicar_mascara_cep)
        grupo_layout.addWidget(self.campos['cep'], 3, 1)
        
        self.btn_consultar_cep = QPushButton("Consultar CEP")
        self.btn_consultar_cep.setStyleSheet("""
            QPushButton {
                background-color: #2980b9;
                color: white;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3498db;
            }
            QPushButton:disabled {
                background-color: #1a1a1a;
                color: #7f8c8d;
            }
        """)
        self.btn_consultar_cep.clicked.connect(self.consultar_cep)
        grupo_layout.addWidget(self.btn_consultar_cep, 3, 2)
        
        # Logradouro
        grupo_layout.addWidget(QLabel("Logradouro:"), 4, 0)
        self.campos['logradouro'] = QLineEdit()
        self.campos['logradouro'].setPlaceholderText("Digite o logradouro")
        self.campos['logradouro'].setReadOnly(True)
        grupo_layout.addWidget(self.campos['logradouro'], 4, 1, 1, 3)
        
        # Número e Complemento
        grupo_layout.addWidget(QLabel("Número:"), 5, 0)
        self.campos['numero'] = QLineEdit()
        self.campos['numero'].setPlaceholderText("Número")
        grupo_layout.addWidget(self.campos['numero'], 5, 1)
        
        grupo_layout.addWidget(QLabel("Complemento:"), 5, 2)
        self.campos['complemento'] = QLineEdit()
        self.campos['complemento'].setPlaceholderText("Complemento")
        grupo_layout.addWidget(self.campos['complemento'], 5, 3)
        
        # Bairro
        grupo_layout.addWidget(QLabel("Bairro:"), 6, 0)
        self.campos['bairro'] = QLineEdit()
        self.campos['bairro'].setPlaceholderText("Digite o bairro")
        self.campos['bairro'].setReadOnly(True)
        grupo_layout.addWidget(self.campos['bairro'], 6, 1, 1, 3)
        
        # Cidade e Estado
        grupo_layout.addWidget(QLabel("Cidade:"), 7, 0)
        self.campos['cidade'] = QLineEdit()
        self.campos['cidade'].setPlaceholderText("Digite a cidade")
        self.campos['cidade'].setReadOnly(True)
        grupo_layout.addWidget(self.campos['cidade'], 7, 1)
        
        grupo_layout.addWidget(QLabel("Estado:"), 7, 2)
        self.campos['estado'] = QLineEdit()
        self.campos['estado'].setPlaceholderText("UF")
        self.campos['estado'].setMaxLength(2)
        self.campos['estado'].setReadOnly(True)
        self.campos['estado'].textChanged.connect(lambda t: self.campos['estado'].setText(t.upper()))
        grupo_layout.addWidget(self.campos['estado'], 7, 3)
        
        grupo.setLayout(grupo_layout)
        layout.addWidget(grupo)
        
        # Botões
        area_botoes = QHBoxLayout()
        area_botoes.setSpacing(10)
        
        btn_limpar = QPushButton("Limpar")
        btn_limpar.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3a;
                color: #e0e0e0;
                padding: 10px 25px;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
            }
        """)
        btn_limpar.clicked.connect(self.limpar_formulario)
        area_botoes.addWidget(btn_limpar)
        
        self.btn_cancelar = QPushButton("Cancelar Edição")
        self.btn_cancelar.setStyleSheet("""
            QPushButton {
                background-color: #c0392b;
                color: white;
                padding: 10px 25px;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e74c3c;
            }
        """)
        self.btn_cancelar.clicked.connect(self.cancelar_edicao)
        self.btn_cancelar.hide()
        area_botoes.addWidget(self.btn_cancelar)
        
        area_botoes.addStretch()
        
        self.btn_salvar = QPushButton("Salvar Cadastro")
        self.btn_salvar.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 10px 35px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
        """)
        self.btn_salvar.clicked.connect(self.salvar_cadastro)
        area_botoes.addWidget(self.btn_salvar)
        
        layout.addLayout(area_botoes)
    
    def configurar_aba_lista(self):
        layout = QVBoxLayout(self.tab_lista)
        layout.setSpacing(15)
        
        header_lista = QLabel("REGISTROS CADASTRADOS")
        header_lista.setAlignment(Qt.AlignCenter)
        header_lista.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            padding: 12px;
            background-color: #2c2c2c;
            color: #e0e0e0;
            border-radius: 6px;
        """)
        layout.addWidget(header_lista)
        
        area_pesquisa = QHBoxLayout()
        area_pesquisa.setSpacing(10)
        area_pesquisa.addWidget(QLabel("Pesquisar:"))
        
        self.campo_pesquisa = QLineEdit()
        self.campo_pesquisa.setPlaceholderText("Digite nome ou documento...")
        self.campo_pesquisa.textChanged.connect(self.pesquisar_pessoas)
        area_pesquisa.addWidget(self.campo_pesquisa)
        
        btn_atualizar = QPushButton("Atualizar")
        btn_atualizar.setStyleSheet("""
            QPushButton {
                background-color: #2c2c2c;
                color: #e0e0e0;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
        """)
        btn_atualizar.clicked.connect(self.carregar_lista)
        area_pesquisa.addWidget(btn_atualizar)
        
        btn_exportar = QPushButton("Exportar PDF")
        btn_exportar.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad;
                color: white;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #9b59b6;
            }
        """)
        btn_exportar.clicked.connect(self.exportar_pdf)
        area_pesquisa.addWidget(btn_exportar)
        
        layout.addLayout(area_pesquisa)
        
        self.tabela = QTableWidget()
        self.tabela.setColumnCount(6)
        self.tabela.setHorizontalHeaderLabels(["ID", "Nome", "Documento", "E-mail", "Cidade", "Ações"])
        self.tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabela.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.tabela.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.tabela.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.tabela.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        
        self.tabela.setColumnWidth(0, 60)
        self.tabela.setColumnWidth(2, 165)
        self.tabela.setColumnWidth(3, 230)
        self.tabela.setColumnWidth(4, 130)
        self.tabela.setColumnWidth(5, 330)
        
        self.tabela.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tabela.setSortingEnabled(False)
        self.tabela.verticalHeader().setDefaultSectionSize(50)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setStyleSheet("""
            QTableWidget {
                alternate-background-color: #1a1a1a;
            }
        """)
        layout.addWidget(self.tabela)
    
    # ============================================================
    # MÉTODOS DE CONSULTA CEP
    # ============================================================
    
    def consultar_cep(self):
        cep = self.campos['cep'].text().strip()
        
        valido, msg = Validador.validar_cep(cep)
        if not valido:
            QMessageBox.warning(self, "CEP Inválido", msg)
            return
        
        self.limpar_endereco()
        
        self.btn_consultar_cep.setEnabled(False)
        self.btn_consultar_cep.setText("Consultando...")
        
        self.thread_consulta = ConsultaCEPThread(cep)
        self.thread_consulta.resultado.connect(self.preencher_endereco)
        self.thread_consulta.erro.connect(self.erro_consulta_cep)
        self.thread_consulta.finished.connect(self.finalizar_consulta_cep)
        self.thread_consulta.start()
    
    def preencher_endereco(self, dados):
        self.campos['logradouro'].setText(dados.get('logradouro', ''))
        self.campos['bairro'].setText(dados.get('bairro', ''))
        self.campos['cidade'].setText(dados.get('cidade', ''))
        self.campos['estado'].setText(dados.get('estado', ''))
        self.campos['complemento'].setText(dados.get('complemento', ''))
    
    def erro_consulta_cep(self, mensagem):
        QMessageBox.warning(self, "Erro na Consulta", mensagem)
    
    def finalizar_consulta_cep(self):
        self.btn_consultar_cep.setEnabled(True)
        self.btn_consultar_cep.setText("Consultar CEP")
    
    def limpar_endereco(self):
        self.campos['logradouro'].setText("")
        self.campos['bairro'].setText("")
        self.campos['cidade'].setText("")
        self.campos['estado'].setText("")
        self.campos['complemento'].setText("")
    
    # ============================================================
    # MÉTODOS DE MÁSCARA
    # ============================================================
    
    def atualizar_mascara_documento(self, tipo):
        self.campos['documento'].blockSignals(True)
        self.campos['documento'].clear()
        self.campos['documento'].blockSignals(False)
        
        if tipo == "CPF":
            self.campos['documento'].setPlaceholderText("000.000.000-00")
            self.campos['documento'].setMaxLength(14)
        else:
            self.campos['documento'].setPlaceholderText("00.000.000/0000-00")
            self.campos['documento'].setMaxLength(18)
    
    def aplicar_mascara_documento(self, texto):
        digitos = re.sub(r'[^0-9]', '', texto)
        tipo = self.campos['tipo_doc'].currentText()
        
        if tipo == "CPF":
            if len(digitos) <= 3:
                mascara = digitos
            elif len(digitos) <= 6:
                mascara = f"{digitos[:3]}.{digitos[3:]}"
            elif len(digitos) <= 9:
                mascara = f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:]}"
            else:
                mascara = f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:11]}"
        else:
            if len(digitos) <= 2:
                mascara = digitos
            elif len(digitos) <= 5:
                mascara = f"{digitos[:2]}.{digitos[2:]}"
            elif len(digitos) <= 8:
                mascara = f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:]}"
            elif len(digitos) <= 12:
                mascara = f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:]}"
            else:
                mascara = f"{digitos[:2]}.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-{digitos[12:14]}"
        
        if texto != mascara:
            self.campos['documento'].blockSignals(True)
            self.campos['documento'].setText(mascara)
            self.campos['documento'].setCursorPosition(len(mascara))
            self.campos['documento'].blockSignals(False)
    
    def aplicar_mascara_celular(self, texto):
        digitos = re.sub(r'[^0-9]', '', texto)
        if len(digitos) <= 2:
            mascara = f"({digitos}"
        elif len(digitos) <= 6:
            mascara = f"({digitos[:2]}) {digitos[2:]}"
        elif len(digitos) <= 10:
            mascara = f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
        else:
            mascara = f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:11]}"
        
        if texto != mascara:
            self.campos['celular'].blockSignals(True)
            self.campos['celular'].setText(mascara)
            self.campos['celular'].blockSignals(False)
    
    def aplicar_mascara_cep(self, texto):
        digitos = re.sub(r'[^0-9]', '', texto)
        if len(digitos) <= 5:
            mascara = digitos
        else:
            mascara = f"{digitos[:5]}-{digitos[5:8]}"
        
        if texto != mascara:
            self.campos['cep'].blockSignals(True)
            self.campos['cep'].setText(mascara)
            self.campos['cep'].blockSignals(False)
    
    # ============================================================
    # MÉTODOS DE VALIDAÇÃO E SALVAMENTO
    # ============================================================
    
    def validar_todos_campos(self):
        erros = []
        
        valido, msg = Validador.validar_campo_obrigatorio(self.campos['nome'].text(), "Nome")
        if not valido:
            erros.append(msg)
        
        tipo_doc = self.campos['tipo_doc'].currentText()
        doc = self.campos['documento'].text()
        if tipo_doc == "CPF":
            valido, msg = Validador.validar_cpf(doc)
        else:
            valido, msg = Validador.validar_cnpj(doc)
        if not valido:
            erros.append(msg)
        
        valido, msg = Validador.validar_email(self.campos['email'].text())
        if not valido:
            erros.append(msg)
        
        valido, msg = Validador.validar_telefone(self.campos['celular'].text())
        if not valido:
            erros.append(msg)
        
        valido, msg = Validador.validar_cep(self.campos['cep'].text())
        if not valido:
            erros.append(msg)
        
        return erros
    
    def salvar_cadastro(self):
        erros = self.validar_todos_campos()
        
        if erros:
            msg = "\n".join(f"• {erro}" for erro in erros)
            QMessageBox.critical(self, "Erros no Cadastro", 
                                f"Corrija os seguintes erros:\n\n{msg}")
            return
        
        dados = {
            'nome_completo': self.campos['nome'].text().strip(),
            'tipo_documento': self.campos['tipo_doc'].currentText(),
            'documento': self.campos['documento'].text().strip(),
            'email': self.campos['email'].text().strip(),
            'celular': self.campos['celular'].text().strip(),
            'cep': self.campos['cep'].text().strip(),
            'logradouro': self.campos['logradouro'].text().strip(),
            'numero': self.campos['numero'].text().strip(),
            'complemento': self.campos['complemento'].text().strip(),
            'bairro': self.campos['bairro'].text().strip(),
            'cidade': self.campos['cidade'].text().strip(),
            'estado': self.campos['estado'].text().strip().upper()
        }
        
        if self.pessoa_editando:
            sucesso, msg = self.db.atualizar_pessoa(self.pessoa_editando, dados)
        else:
            sucesso, msg = self.db.inserir_pessoa(dados)
        
        if sucesso:
            QMessageBox.information(self, "Sucesso", msg)
            self.limpar_formulario()
            self.carregar_lista()
            self.cancelar_edicao()
        else:
            QMessageBox.critical(self, "Erro", msg)
    
    def limpar_formulario(self):
        for campo in self.campos.values():
            if isinstance(campo, QLineEdit):
                campo.setText("")
            elif isinstance(campo, QComboBox):
                campo.setCurrentIndex(0)
        
        self.limpar_endereco()
        self.pessoa_editando = None
        
        self.btn_cancelar.hide()
        self.btn_salvar.setText("Salvar Cadastro")
        self.setWindowTitle("Sistema de Cadastro")
    
    def cancelar_edicao(self):
        self.limpar_formulario()
        self.carregar_lista()
    
    def carregar_dados_para_edicao(self, dados):
        if not dados:
            return
        
        self.pessoa_editando = dados[0]
        self.campos['nome'].setText(dados[1] or '')
        
        tipo_doc = dados[2] or 'CPF'
        idx = self.campos['tipo_doc'].findText(tipo_doc)
        if idx >= 0:
            self.campos['tipo_doc'].setCurrentIndex(idx)
        self.campos['documento'].setText(dados[3] or '')
        self.campos['email'].setText(dados[4] or '')
        self.campos['celular'].setText(dados[5] or '')
        self.campos['cep'].setText(dados[6] or '')
        self.campos['logradouro'].setText(dados[7] or '')
        self.campos['numero'].setText(dados[8] or '')
        self.campos['complemento'].setText(dados[9] or '')
        self.campos['bairro'].setText(dados[10] or '')
        self.campos['cidade'].setText(dados[11] or '')
        self.campos['estado'].setText(dados[12] or '')
        
        self.campos['logradouro'].setReadOnly(False)
        self.campos['bairro'].setReadOnly(False)
        self.campos['cidade'].setReadOnly(False)
        self.campos['estado'].setReadOnly(False)
        
        self.btn_cancelar.show()
        self.btn_salvar.setText("Atualizar Cadastro")
        self.setWindowTitle("Editando Cadastro")
        self.tabs.setCurrentIndex(0)
    
    # ============================================================
    # MÉTODOS DA LISTA
    # ============================================================
    
    def carregar_lista(self, filtro=""):
        pessoas = self.db.listar_pessoas()
        
        if filtro:
            filtro = filtro.lower()
            pessoas = [p for p in pessoas if 
                      filtro in str(p[1]).lower() or 
                      filtro in str(p[2]).lower()]
        
        self.tabela.setRowCount(len(pessoas))
        
        for i, pessoa in enumerate(pessoas):
            self.tabela.setItem(i, 0, QTableWidgetItem(str(pessoa[0])))
            self.tabela.setItem(i, 1, QTableWidgetItem(pessoa[1] or ''))
            self.tabela.setItem(i, 2, QTableWidgetItem(pessoa[2] or ''))
            self.tabela.setItem(i, 3, QTableWidgetItem(pessoa[3] or ''))
            self.tabela.setItem(i, 4, QTableWidgetItem(pessoa[5] or ''))
            
            widget_acoes = QWidget()
            layout_acoes = QHBoxLayout(widget_acoes)
            layout_acoes.setContentsMargins(6, 6, 6, 6)
            layout_acoes.setSpacing(6)
            layout_acoes.setSizeConstraint(QHBoxLayout.SetFixedSize)
            layout_acoes.setAlignment(Qt.AlignCenter)
            
            btn_editar = QPushButton("Editar")
            btn_editar.setFixedSize(92, 34)
            btn_editar.setStyleSheet("""
                QPushButton {
                    background-color: #2980b9;
                    color: white;
                    border: none;
                    padding: 5px 8px;
                    border-radius: 3px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #3498db;
                }
            """)
            btn_editar.clicked.connect(lambda checked, id=pessoa[0]: self.editar_pessoa(id))
            
            btn_detalhes = QPushButton("Detalhes")
            btn_detalhes.setFixedSize(110, 34)
            btn_detalhes.setStyleSheet("""
                QPushButton {
                    background-color: #27ae60;
                    color: white;
                    border: none;
                    padding: 5px 8px;
                    border-radius: 3px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #2ecc71;
                }
            """)
            btn_detalhes.clicked.connect(lambda checked, id=pessoa[0]: self.ver_detalhes(id))
            
            btn_excluir = QPushButton("Excluir")
            btn_excluir.setFixedSize(92, 34)
            btn_excluir.setStyleSheet("""
                QPushButton {
                    background-color: #c0392b;
                    color: white;
                    border: none;
                    padding: 5px 8px;
                    border-radius: 3px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #e74c3c;
                }
            """)
            btn_excluir.clicked.connect(lambda checked, id=pessoa[0]: self.excluir_pessoa(id))
            
            layout_acoes.addWidget(btn_editar)
            layout_acoes.addWidget(btn_detalhes)
            layout_acoes.addWidget(btn_excluir)
            
            self.tabela.setCellWidget(i, 5, widget_acoes)
    
    def pesquisar_pessoas(self, texto):
        self.carregar_lista(texto)
    
    def editar_pessoa(self, id_pessoa):
        dados = self.db.buscar_pessoa(id_pessoa)
        if dados:
            self.carregar_dados_para_edicao(dados)
    
    def ver_detalhes(self, id_pessoa):
        dados = self.db.buscar_pessoa(id_pessoa)
        if dados:
            dialog = DetalhesPessoaDialog(dados, self)
            dialog.exec()
    
    def excluir_pessoa(self, id_pessoa):
        dados = self.db.buscar_pessoa(id_pessoa)
        if not dados:
            return
        
        confirm = QMessageBox.question(
            self, "Confirmar Exclusão",
            f"Tem certeza que deseja excluir o cadastro de\n\n'{dados[1]}'?\n\nEsta ação não pode ser desfeita.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            sucesso, msg = self.db.excluir_pessoa(id_pessoa)
            if sucesso:
                QMessageBox.information(self, "Sucesso", msg)
                self.carregar_lista()
            else:
                QMessageBox.critical(self, "Erro", msg)
    
    # ============================================================
    # EXPORTAÇÃO PDF
    # ============================================================
    
    def exportar_pdf(self):
        pessoas = self.db.listar_todas_pessoas()
        if not pessoas:
            QMessageBox.warning(self, "Sem dados",
                                "Não há registros para exportar.")
            return
        
        nome_arquivo = f"cadastros_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar PDF", nome_arquivo, "Arquivos PDF (*.pdf)"
        )
        if not caminho:
            return
        if not caminho.lower().endswith(".pdf"):
            caminho += ".pdf"
        
        try:
            self._gerar_pdf(caminho, pessoas)
            resposta = QMessageBox.question(
                self, "PDF Gerado",
                f"PDF salvo com sucesso em:\n{caminho}\n\nDeseja abrir o arquivo agora?",
                QMessageBox.Yes | QMessageBox.No
            )
            if resposta == QMessageBox.Yes:
                self._abrir_arquivo(caminho)
        except Exception as e:
            QMessageBox.critical(self, "Erro",
                                 f"Falha ao gerar PDF:\n{str(e)}")
    
    def _abrir_arquivo(self, caminho):
        try:
            sistema = platform.system()
            if sistema == "Windows":
                os.startfile(caminho)  # type: ignore
            elif sistema == "Darwin":
                subprocess.Popen(["open", caminho])
            else:
                subprocess.Popen(["xdg-open", caminho])
        except Exception as e:
            QMessageBox.warning(self, "Aviso",
                                f"Não foi possível abrir o arquivo:\n{e}")
    
    def _gerar_pdf(self, caminho, pessoas):
        doc = SimpleDocTemplate(
            caminho, pagesize=landscape(A4),
            leftMargin=1.2 * cm, rightMargin=1.2 * cm,
            topMargin=1.2 * cm, bottomMargin=1.2 * cm,
            title="Lista de Cadastros", author="Sistema de Cadastro"
        )
        
        styles = getSampleStyleSheet()
        titulo_style = ParagraphStyle(
            "Titulo", parent=styles["Title"],
            fontSize=18, leading=22,
            textColor=colors.HexColor("#1f2d3d"),
            alignment=TA_CENTER, spaceAfter=4
        )
        sub_style = ParagraphStyle(
            "Sub", parent=styles["Normal"],
            fontSize=9, textColor=colors.HexColor("#666666"),
            alignment=TA_CENTER, spaceAfter=14
        )
        header_style = ParagraphStyle(
            "Header", parent=styles["Normal"],
            fontName="Helvetica-Bold", fontSize=8, leading=10,
            textColor=colors.white, alignment=TA_CENTER
        )
        cell_style = ParagraphStyle(
            "Cell", parent=styles["Normal"],
            fontName="Helvetica", fontSize=7.5, leading=9
        )
        
        elementos = [
            Paragraph("LISTA DE CADASTROS", titulo_style),
            Paragraph(
                f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} "
                f"&nbsp;&nbsp;•&nbsp;&nbsp; Total de {len(pessoas)} registro(s)",
                sub_style
            )
        ]
        
        headers = ["ID", "Nome Completo", "Tipo", "Documento", "E-mail",
                   "Celular", "CEP", "Logradouro", "Nº", "Comp.",
                   "Bairro", "Cidade", "UF", "Cadastro"]
        
        data = [[Paragraph(h, header_style) for h in headers]]
        
        for p in pessoas:
            data_cad = ""
            if p[13]:
                try:
                    data_cad = datetime.fromisoformat(p[13]).strftime("%d/%m/%Y")
                except Exception:
                    data_cad = str(p[13])
            
            linha = [
                Paragraph(str(p[0] or ""), cell_style),
                Paragraph(str(p[1] or ""), cell_style),
                Paragraph(str(p[2] or ""), cell_style),
                Paragraph(str(p[3] or ""), cell_style),
                Paragraph(str(p[4] or ""), cell_style),
                Paragraph(str(p[5] or ""), cell_style),
                Paragraph(str(p[6] or ""), cell_style),
                Paragraph(str(p[7] or ""), cell_style),
                Paragraph(str(p[8] or ""), cell_style),
                Paragraph(str(p[9] or ""), cell_style),
                Paragraph(str(p[10] or ""), cell_style),
                Paragraph(str(p[11] or ""), cell_style),
                Paragraph(str(p[12] or ""), cell_style),
                Paragraph(data_cad, cell_style),
            ]
            data.append(linha)
        
        col_widths = [
            1.0 * cm, 4.2 * cm, 1.2 * cm, 2.6 * cm, 4.5 * cm,
            2.4 * cm, 1.9 * cm, 3.4 * cm, 1.0 * cm, 1.6 * cm,
            2.4 * cm, 2.2 * cm, 0.9 * cm, 1.7 * cm,
        ]
        
        tabela = Table(data, colWidths=col_widths, repeatRows=1)
        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("ALIGN",      (0, 0), (-1, 0), "CENTER"),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bdc3c7")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                [colors.white, colors.HexColor("#f4f6f7")]),
        ]))
        
        elementos.append(tabela)
        elementos.append(Spacer(1, 0.4 * cm))
        elementos.append(Paragraph(
            "<font color='#888888' size='7'>"
            "Documento gerado automaticamente pelo Sistema de Cadastro."
            "</font>",
            styles["Normal"]
        ))
        
        doc.build(elementos)
    
    def closeEvent(self, event):
        self.db.fechar()
        event.accept()


# ============================================================
# PONTO DE ENTRADA
# ============================================================

def main():
    app = QApplication(sys.argv)
    
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()