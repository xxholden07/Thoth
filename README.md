# 📚 Biblioteca de Livros PDF

Sistema de gerenciamento de biblioteca pessoal para livros em PDF com banco de dados SQLite.

## 🚀 Funcionalidades

- ✅ Upload de arquivos PDF
- ✅ Extração automática de metadados (título, autor, páginas)
- ✅ Armazenamento em banco de dados SQLite
- ✅ Busca por título ou autor
- ✅ Filtro por categoria
- ✅ Edição de informações dos livros
- ✅ Exclusão de livros
- ✅ Estatísticas da biblioteca
- ✅ Gráficos de visualização
- ✅ Detecção de duplicatas por hash MD5

## 📋 Pré-requisitos

- Python 3.8 ou superior
- pip (gerenciador de pacotes Python)

## 🔧 Instalação Local

1. Clone ou baixe este projeto

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Execute o aplicativo:
```bash
streamlit run app.py
```

4. Acesse no navegador: `http://localhost:8501`

## ☁️ Deploy no Streamlit Cloud

1. Faça login em [share.streamlit.io](https://share.streamlit.io)

2. Conecte sua conta do GitHub

3. Crie um novo repositório no GitHub com os arquivos:
   - `app.py`
   - `requirements.txt`
   - `README.md`

4. No Streamlit Cloud, clique em "New app"

5. Selecione seu repositório e branch

6. Defina o arquivo principal: `app.py`

7. Clique em "Deploy"

## 📖 Como Usar

### Adicionar Livros
1. Selecione "📥 Adicionar Livro" no menu lateral
2. Faça upload do arquivo PDF
3. Preencha as informações (título é obrigatório)
4. Clique em "💾 Salvar na Biblioteca"

### Gerenciar Biblioteca
1. Selecione "📖 Biblioteca" no menu lateral
2. Use a busca para encontrar livros
3. Filtre por categoria
4. Edite ou delete livros conforme necessário

### Ver Estatísticas
1. Selecione "📊 Estatísticas" no menu lateral
2. Visualize métricas e gráficos da sua biblioteca

## 💾 Banco de Dados

O sistema cria automaticamente um arquivo `biblioteca.db` que armazena:
- Título, autor, ano, categoria
- Idioma, número de páginas
- Hash do arquivo (para evitar duplicatas)
- Nome do arquivo original
- Data de adição
- Notas personalizadas

## 🔒 Segurança

- Detecção de arquivos duplicados via hash MD5
- Validação de tipo de arquivo (apenas PDF)
- Armazenamento local dos metadados

## 📝 Notas

- Os arquivos PDF **não são armazenados** no banco de dados, apenas os metadados
- O banco de dados SQLite é criado na mesma pasta do aplicativo
- Para backup, copie o arquivo `biblioteca.db`

## 🤝 Contribuições

Sugestões e melhorias são bem-vindas!

## 📄 Licença

Este projeto é de código aberto e está disponível sob a licença MIT.
