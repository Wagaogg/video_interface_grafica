

# Sistema de Cadastro de Pessoas

Sistema desktop desenvolvido em Python com PySide6 para cadastro e gerenciamento de pessoas com integração à API ViaCEP.

## 📋 Funcionalidades

### Cadastro de Pessoas
- Nome completo
- CPF ou CNPJ (com máscara e validação matemática)
- E-mail (com validação de formato)
- Celular (com máscara)
- CEP (com máscara)
- Endereço completo (Logradouro, Número, Complemento, Bairro, Cidade, Estado)

### Consulta de CEP
- Integração com a API ViaCEP
- Preenchimento automático de: Logradouro, Bairro, Cidade, Estado
- Tratamento de erros: CEP inexistente, problemas de conexão, API indisponível

### Validações
- Campos obrigatórios
- CPF válido (dígitos verificadores)
- CNPJ válido (dígitos verificadores)
- E-mail com formato correto
- Celular com formato correto
- CEP com formato correto
- Mensagens específicas para cada erro

### Gerenciamento (Desafio Adicional)
- Lista de cadastros em tabela
- Pesquisa por nome ou documento
- Edição de cadastros
- Exclusão de cadastros
- Visualização de detalhes
- Máscaras nos campos de entrada

---

## 🚀 Como Executar

### 1. Instalar o Python
- Baixe e instale o Python 3.8 ou superior: https://www.python.org/downloads/
- **IMPORTANTE:** Durante a instalação, marque a opção **"Add Python to PATH"**

### 2. Baixar os arquivos do projeto
- Baixe todos os arquivos do projeto (main.py, requirements.txt, README.md)
- Coloque todos em uma mesma pasta

### 3. Instalar as dependências
Abra o terminal (CMD/PowerShell) na pasta do projeto e execute:

pip install -r requirements.txt