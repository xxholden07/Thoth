import streamlit as st
import sqlite3
import os
from datetime import datetime
import PyPDF2
import io
import hashlib
import requests
import json

# Configuração da página
st.set_page_config(
    page_title="Biblioteca de Livros PDF",
    page_icon="📚",
    layout="wide"
)

# Inicializar banco de dados
def init_database():
    conn = sqlite3.connect('biblioteca.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS livros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            autor TEXT,
            ano INTEGER,
            categoria TEXT,
            idioma TEXT,
            num_paginas INTEGER,
            tamanho_kb INTEGER,
            hash_arquivo TEXT UNIQUE,
            nome_arquivo TEXT,
            data_adicao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notas TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Extrair metadados do PDF
def extrair_metadata_pdf(pdf_file):
    try:
        pdf_file.seek(0)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        metadata = {
            'num_paginas': len(pdf_reader.pages),
            'titulo': '',
            'autor': ''
        }
        
        # Tentar extrair metadados se disponíveis
        if pdf_reader.metadata:
            metadata['titulo'] = pdf_reader.metadata.get('/Title', '') or ''
            metadata['autor'] = pdf_reader.metadata.get('/Author', '') or ''
        
        return metadata
    except Exception as e:
        st.error(f"Erro ao extrair metadados: {str(e)}")
        return {'num_paginas': 0, 'titulo': '', 'autor': ''}

# Calcular hash do arquivo
def calcular_hash(file_bytes):
    return hashlib.md5(file_bytes).hexdigest()

# Buscar livros na Google Books API
def obter_token_service_account():
    """Obtém token de acesso OAuth2 usando credenciais da conta de serviço"""
    service_account_info = st.session_state.get('service_account_json', None)
    
    if not service_account_info:
        return None
    
    try:
        import time
        import base64
        from urllib.parse import urlencode
        
        # Criar JWT
        header = {
            "alg": "RS256",
            "typ": "JWT"
        }
        
        now = int(time.time())
        claim_set = {
            "iss": service_account_info["client_email"],
            "scope": "https://www.googleapis.com/auth/books",
            "aud": "https://oauth2.googleapis.com/token",
            "exp": now + 3600,
            "iat": now
        }
        
        # Usar biblioteca PyJWT se disponível, senão retornar None
        try:
            import jwt
            private_key = service_account_info["private_key"]
            token = jwt.encode(claim_set, private_key, algorithm="RS256", headers=header)
            
            # Trocar JWT por token de acesso
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": token
            }
            
            response = requests.post(token_url, data=data)
            if response.status_code == 200:
                return response.json().get("access_token")
        except ImportError:
            st.warning("⚠️ Biblioteca PyJWT não instalada. Use chave API ao invés de conta de serviço.")
            return None
    except Exception as e:
        st.error(f"Erro ao obter token: {str(e)}")
        return None

def buscar_google_books(query, max_results=10):
    # Tentar usar token de conta de serviço primeiro
    access_token = obter_token_service_account()
    
    if access_token:
        # Usar token OAuth2
        url = f'https://www.googleapis.com/books/v1/volumes?q={query}&maxResults={max_results}'
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get('items', [])
            elif response.status_code == 403:
                st.error("⚠️ Erro de autorização. Verifique as permissões da conta de serviço.")
                return []
            else:
                st.error(f"Erro na busca: {response.status_code}")
                return []
        except Exception as e:
            st.error(f"Erro ao buscar livros: {str(e)}")
            return []
    
    # Caso contrário, tentar usar chave API
    api_key = st.session_state.get('google_api_key', '')
    
    if api_key:
        url = f'https://www.googleapis.com/books/v1/volumes?q={query}&maxResults={max_results}&key={api_key}'
    else:
        url = f'https://www.googleapis.com/books/v1/volumes?q={query}&maxResults={max_results}'
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('items', [])
        elif response.status_code == 403:
            st.error("⚠️ Limite de requisições atingido ou chave API inválida. Configure sua chave API ou conta de serviço nas configurações.")
            return []
        else:
            st.error(f"Erro na busca: {response.status_code}")
            return []
    except requests.exceptions.Timeout:
        st.error("⏱️ Tempo de espera esgotado. Tente novamente.")
        return []
    except Exception as e:
        st.error(f"Erro ao buscar livros: {str(e)}")
        return []

# Salvar arquivo PDF no disco
def salvar_pdf(file_bytes, hash_arquivo):
    # Criar diretório pdfs se não existir
    if not os.path.exists('pdfs'):
        os.makedirs('pdfs')
    
    # Salvar arquivo com o hash como nome
    caminho_arquivo = os.path.join('pdfs', f'{hash_arquivo}.pdf')
    with open(caminho_arquivo, 'wb') as f:
        f.write(file_bytes)
    return caminho_arquivo

# Carregar arquivo PDF do disco
def carregar_pdf(hash_arquivo):
    caminho_arquivo = os.path.join('pdfs', f'{hash_arquivo}.pdf')
    if os.path.exists(caminho_arquivo):
        with open(caminho_arquivo, 'rb') as f:
            return f.read()
    return None

# Adicionar livro ao banco de dados
def adicionar_livro(dados_livro, file_bytes=None):
    try:
        conn = sqlite3.connect('biblioteca.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO livros (titulo, autor, ano, categoria, idioma, num_paginas, 
                               tamanho_kb, hash_arquivo, nome_arquivo, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            dados_livro['titulo'],
            dados_livro['autor'],
            dados_livro['ano'],
            dados_livro['categoria'],
            dados_livro['idioma'],
            dados_livro['num_paginas'],
            dados_livro['tamanho_kb'],
            dados_livro['hash_arquivo'],
            dados_livro['nome_arquivo'],
            dados_livro['notas']
        ))
        conn.commit()
        conn.close()
        
        # Salvar arquivo PDF se fornecido
        if file_bytes:
            salvar_pdf(file_bytes, dados_livro['hash_arquivo'])
        
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        st.error(f"Erro ao adicionar livro: {str(e)}")
        return False

# Buscar livros
def buscar_livros(filtro='', categoria='Todas'):
    conn = sqlite3.connect('biblioteca.db')
    c = conn.cursor()
    
    if categoria == 'Todas':
        c.execute('''
            SELECT * FROM livros 
            WHERE titulo LIKE ? OR autor LIKE ?
            ORDER BY data_adicao DESC
        ''', (f'%{filtro}%', f'%{filtro}%'))
    else:
        c.execute('''
            SELECT * FROM livros 
            WHERE (titulo LIKE ? OR autor LIKE ?) AND categoria = ?
            ORDER BY data_adicao DESC
        ''', (f'%{filtro}%', f'%{filtro}%', categoria))
    
    livros = c.fetchall()
    conn.close()
    return livros

# Obter categorias únicas
def obter_categorias():
    conn = sqlite3.connect('biblioteca.db')
    c = conn.cursor()
    c.execute('SELECT DISTINCT categoria FROM livros WHERE categoria IS NOT NULL ORDER BY categoria')
    categorias = [row[0] for row in c.fetchall()]
    conn.close()
    return categorias

# Deletar livro
def deletar_livro(livro_id):
    conn = sqlite3.connect('biblioteca.db')
    c = conn.cursor()
    
    # Obter hash do arquivo antes de deletar
    c.execute('SELECT hash_arquivo FROM livros WHERE id = ?', (livro_id,))
    resultado = c.fetchone()
    
    if resultado:
        hash_arquivo = resultado[0]
        # Deletar arquivo PDF se existir
        caminho_arquivo = os.path.join('pdfs', f'{hash_arquivo}.pdf')
        if os.path.exists(caminho_arquivo):
            os.remove(caminho_arquivo)
    
    c.execute('DELETE FROM livros WHERE id = ?', (livro_id,))
    conn.commit()
    conn.close()

# Atualizar livro
def atualizar_livro(livro_id, dados_livro):
    conn = sqlite3.connect('biblioteca.db')
    c = conn.cursor()
    c.execute('''
        UPDATE livros 
        SET titulo=?, autor=?, ano=?, categoria=?, idioma=?, notas=?
        WHERE id=?
    ''', (
        dados_livro['titulo'],
        dados_livro['autor'],
        dados_livro['ano'],
        dados_livro['categoria'],
        dados_livro['idioma'],
        dados_livro['notas'],
        livro_id
    ))
    conn.commit()
    conn.close()

# Obter estatísticas
def obter_estatisticas():
    conn = sqlite3.connect('biblioteca.db')
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM livros')
    total_livros = c.fetchone()[0]
    
    c.execute('SELECT SUM(num_paginas) FROM livros')
    total_paginas = c.fetchone()[0] or 0
    
    c.execute('SELECT COUNT(DISTINCT autor) FROM livros WHERE autor IS NOT NULL AND autor != ""')
    total_autores = c.fetchone()[0]
    
    c.execute('SELECT COUNT(DISTINCT categoria) FROM livros WHERE categoria IS NOT NULL AND categoria != ""')
    total_categorias = c.fetchone()[0]
    
    conn.close()
    
    return {
        'total_livros': total_livros,
        'total_paginas': total_paginas,
        'total_autores': total_autores,
        'total_categorias': total_categorias
    }

# Inicializar banco de dados
init_database()

# Interface principal
st.title("📚 Biblioteca de Livros PDF")
st.markdown("### Bem-vinda, Skárlath! 🦅")
st.markdown("---")

# Menu lateral
menu = st.sidebar.selectbox(
    "Menu",
    ["📥 Adicionar Livro", "📖 Biblioteca", "🔍 Buscar no Google Books", "📊 Estatísticas", "⚙️ Configurações"]
)

if menu == "📥 Adicionar Livro":
    st.header("Adicionar Novo Livro")
    
    uploaded_file = st.file_uploader("Selecione um arquivo PDF", type=['pdf'])
    
    if uploaded_file:
        # Ler arquivo
        file_bytes = uploaded_file.read()
        file_size_kb = len(file_bytes) // 1024
        file_hash = calcular_hash(file_bytes)
        
        # Extrair metadados
        uploaded_file.seek(0)
        metadata = extrair_metadata_pdf(uploaded_file)
        
        st.success(f"Arquivo carregado: {uploaded_file.name} ({file_size_kb} KB)")
        
        col1, col2 = st.columns(2)
        
        with col1:
            titulo = st.text_input("Título *", value=metadata['titulo'] or uploaded_file.name.replace('.pdf', ''))
            autor = st.text_input("Autor", value=metadata['autor'])
            ano = st.number_input("Ano de Publicação", min_value=1000, max_value=2100, value=datetime.now().year, step=1)
        
        with col2:
            categoria = st.text_input("Categoria", placeholder="Ex: Ficção, Técnico, Romance...")
            idioma = st.selectbox("Idioma", ["Português", "Inglês", "Espanhol", "Francês", "Alemão", "Outro"])
            st.metric("Páginas", metadata['num_paginas'])
        
        notas = st.text_area("Notas/Observações", placeholder="Adicione anotações sobre o livro...")
        
        if st.button("💾 Salvar na Biblioteca", type="primary"):
            if titulo:
                dados_livro = {
                    'titulo': titulo,
                    'autor': autor or None,
                    'ano': ano,
                    'categoria': categoria or None,
                    'idioma': idioma,
                    'num_paginas': metadata['num_paginas'],
                    'tamanho_kb': file_size_kb,
                    'hash_arquivo': file_hash,
                    'nome_arquivo': uploaded_file.name,
                    'notas': notas or None
                }
                
                if adicionar_livro(dados_livro, file_bytes):
                    st.success("✅ Livro adicionado com sucesso!")
                    st.balloons()
                else:
                    st.error("❌ Este livro já existe na biblioteca!")
            else:
                st.error("Por favor, preencha o título do livro.")

elif menu == "📖 Biblioteca":
    st.header("Minha Biblioteca")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        filtro = st.text_input("🔍 Buscar por título ou autor")
    with col2:
        categorias = ['Todas'] + obter_categorias()
        categoria_filtro = st.selectbox("Categoria", categorias)
    
    livros = buscar_livros(filtro, categoria_filtro)
    
    if livros:
        st.info(f"📚 {len(livros)} livro(s) encontrado(s)")
        
        for livro in livros:
            with st.expander(f"📖 {livro[1]} - {livro[2] or 'Autor desconhecido'}"):
                st.write(f"**Título:** {livro[1]}")
                st.write(f"**Autor:** {livro[2] or 'Autor desconhecido'}")
                
                if livro[11]:
                    st.write(f"**Notas:** {livro[11]}")
                
                # Botões de ação
                col_download, col_edit, col_delete = st.columns(3)
                
                with col_download:
                    # Botão de download
                    pdf_bytes = carregar_pdf(livro[8])  # livro[8] é o hash_arquivo
                    if pdf_bytes:
                        st.download_button(
                            label="📥 Download",
                            data=pdf_bytes,
                            file_name=livro[9],  # livro[9] é o nome_arquivo
                            mime="application/pdf",
                            key=f"download_{livro[0]}"
                        )
                    else:
                        st.button(f"📥 Indisponível", key=f"download_{livro[0]}", disabled=True)
                
                with col_edit:
                    if st.button(f"✏️ Editar", key=f"edit_{livro[0]}"):
                        st.session_state[f'editing_{livro[0]}'] = True
                
                with col_delete:
                    if st.button(f"🗑️ Deletar", key=f"delete_{livro[0]}"):
                        deletar_livro(livro[0])
                        st.success("Livro deletado!")
                        st.rerun()
                
                # Formulário de edição
                if st.session_state.get(f'editing_{livro[0]}', False):
                    st.markdown("---")
                    st.subheader("Editar Livro")
                    
                    edit_col1, edit_col2 = st.columns(2)
                    
                    with edit_col1:
                        novo_titulo = st.text_input("Título", value=livro[1], key=f"titulo_{livro[0]}")
                        novo_autor = st.text_input("Autor", value=livro[2] or "", key=f"autor_{livro[0]}")
                        novo_ano = st.number_input("Ano", value=livro[3] or datetime.now().year, key=f"ano_{livro[0]}")
                    
                    with edit_col2:
                        nova_categoria = st.text_input("Categoria", value=livro[4] or "", key=f"cat_{livro[0]}")
                        novo_idioma = st.selectbox("Idioma", 
                                                   ["Português", "Inglês", "Espanhol", "Francês", "Alemão", "Outro"],
                                                   index=["Português", "Inglês", "Espanhol", "Francês", "Alemão", "Outro"].index(livro[5]) if livro[5] in ["Português", "Inglês", "Espanhol", "Francês", "Alemão", "Outro"] else 0,
                                                   key=f"idioma_{livro[0]}")
                    
                    novas_notas = st.text_area("Notas", value=livro[11] or "", key=f"notas_{livro[0]}")
                    
                    col_save, col_cancel = st.columns(2)
                    
                    with col_save:
                        if st.button("💾 Salvar Alterações", key=f"save_{livro[0]}"):
                            dados_atualizados = {
                                'titulo': novo_titulo,
                                'autor': novo_autor or None,
                                'ano': novo_ano,
                                'categoria': nova_categoria or None,
                                'idioma': novo_idioma,
                                'notas': novas_notas or None
                            }
                            atualizar_livro(livro[0], dados_atualizados)
                            st.session_state[f'editing_{livro[0]}'] = False
                            st.success("Livro atualizado!")
                            st.rerun()
                    
                    with col_cancel:
                        if st.button("❌ Cancelar", key=f"cancel_{livro[0]}"):
                            st.session_state[f'editing_{livro[0]}'] = False
                            st.rerun()
    else:
        st.info("📭 Nenhum livro encontrado. Adicione seus primeiros livros!")

elif menu == "� Buscar no Google Books":
    st.header("Buscar Livros no Google Books")
    
    busca = st.text_input("🔍 Digite o título, autor ou ISBN do livro", placeholder="Ex: Harry Potter, J.K. Rowling, ISBN...")
    
    if st.button("🔎 Buscar", type="primary"):
        if busca:
            with st.spinner("Buscando livros..."):
                resultados = buscar_google_books(busca)
                
                if resultados:
                    st.success(f"✅ {len(resultados)} livro(s) encontrado(s)")
                    
                    for item in resultados:
                        volume_info = item.get('volumeInfo', {})
                        
                        titulo = volume_info.get('title', 'Sem título')
                        autores = volume_info.get('authors', [])
                        autor = ', '.join(autores) if autores else 'Autor desconhecido'
                        ano = volume_info.get('publishedDate', '')[:4] if volume_info.get('publishedDate') else None
                        categoria = ', '.join(volume_info.get('categories', [])) if volume_info.get('categories') else None
                        idioma = volume_info.get('language', 'Desconhecido')
                        num_paginas = volume_info.get('pageCount', 0)
                        descricao = volume_info.get('description', '')
                        thumbnail = volume_info.get('imageLinks', {}).get('thumbnail', '')
                        
                        with st.expander(f"📖 {titulo} - {autor}"):
                            col1, col2 = st.columns([1, 3])
                            
                            with col1:
                                if thumbnail:
                                    st.image(thumbnail, width=100)
                            
                            with col2:
                                st.write(f"**Título:** {titulo}")
                                st.write(f"**Autor(es):** {autor}")
                                if ano:
                                    st.write(f"**Ano:** {ano}")
                                if categoria:
                                    st.write(f"**Categoria:** {categoria}")
                                st.write(f"**Idioma:** {idioma}")
                                st.write(f"**Páginas:** {num_paginas if num_paginas else 'N/A'}")
                            
                            if descricao:
                                st.write("**Descrição:**")
                                st.write(descricao[:300] + "..." if len(descricao) > 300 else descricao)
                            
                            st.markdown("---")
                            st.info("💡 Para adicionar este livro, faça o upload do PDF na seção 'Adicionar Livro' e use estas informações.")
                            
                            # Botão para copiar informações
                            if st.button("📋 Copiar Informações", key=f"copy_{item.get('id')}"):
                                info_texto = f"Título: {titulo}\nAutor: {autor}"
                                if ano:
                                    info_texto += f"\nAno: {ano}"
                                if categoria:
                                    info_texto += f"\nCategoria: {categoria}"
                                st.code(info_texto)
                                st.success("✅ Informações prontas para copiar!")
                else:
                    st.warning("⚠️ Nenhum livro encontrado. Tente outro termo de busca.")
        else:
            st.error("Por favor, digite algo para buscar.")

elif menu == "�📊 Estatísticas":
    st.header("Estatísticas da Biblioteca")
    
    stats = obter_estatisticas()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📚 Total de Livros", stats['total_livros'])
    
    with col2:
        st.metric("📄 Total de Páginas", f"{stats['total_paginas']:,}")
    
    with col3:
        st.metric("✍️ Autores Únicos", stats['total_autores'])
    
    with col4:
        st.metric("🏷️ Categorias", stats['total_categorias'])
    
    st.markdown("---")
    
    # Gráficos
    if stats['total_livros'] > 0:
        conn = sqlite3.connect('biblioteca.db')
        c = conn.cursor()
        
        # Livros por categoria
        st.subheader("📊 Livros por Categoria")
        c.execute('''
            SELECT categoria, COUNT(*) as total 
            FROM livros 
            WHERE categoria IS NOT NULL AND categoria != ""
            GROUP BY categoria 
            ORDER BY total DESC
        ''')
        categorias_data = c.fetchall()
        
        if categorias_data:
            import pandas as pd
            df_categorias = pd.DataFrame(categorias_data, columns=['Categoria', 'Quantidade'])
            st.bar_chart(df_categorias.set_index('Categoria'))
        
        # Livros por ano
        st.subheader("📅 Livros por Ano de Publicação")
        c.execute('''
            SELECT ano, COUNT(*) as total 
            FROM livros 
            WHERE ano IS NOT NULL
            GROUP BY ano 
            ORDER BY ano DESC
        ''')
        anos_data = c.fetchall()
        
        if anos_data:
            df_anos = pd.DataFrame(anos_data, columns=['Ano', 'Quantidade'])
            st.line_chart(df_anos.set_index('Ano'))
        
        conn.close()

elif menu == "⚙️ Configurações":
    st.header("Configurações")
    
    st.subheader("🔑 Autenticação Google Books API")
    st.markdown("""
    Escolha um dos métodos de autenticação:
    """)
    
    # Tabs para diferentes métodos de autenticação
    tab1, tab2 = st.tabs(["🔑 Chave API", "👤 Conta de Serviço"])
    
    with tab1:
        st.markdown("""
        **Chave API (mais simples)**
        
        1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
        2. Selecione seu projeto (ex: scribe-457513)
        3. Ative a **Books API**
        4. Vá em "APIs & Services" > "Credentials"
        5. Crie uma "API Key"
        6. Cole a chave abaixo
        """)
        
        chave_atual = st.session_state.get('google_api_key', '')
        
        api_key_input = st.text_input(
            "Chave API do Google Books",
            value=chave_atual,
            type="password",
            help="Sua chave API do Google Cloud com Books API habilitada"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💾 Salvar Chave API", type="primary"):
                if api_key_input:
                    st.session_state['google_api_key'] = api_key_input
                    st.session_state['service_account_json'] = None  # Limpar conta de serviço
                    st.success("✅ Chave API salva com sucesso!")
                    st.info("💡 A chave será válida durante esta sessão.")
                else:
                    st.error("❌ Por favor, insira uma chave válida.")
        
        with col2:
            if st.button("🗑️ Remover Chave API"):
                st.session_state['google_api_key'] = ''
                st.success("✅ Chave removida.")
    
    with tab2:
        st.markdown("""
        **Conta de Serviço (recomendado para produção)**
        
        1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
        2. Selecione seu projeto (ex: scribe-457513)
        3. Vá em "IAM & Admin" > "Service Accounts"
        4. Selecione ou crie uma conta de serviço
        5. Crie uma chave JSON
        6. Faça upload do arquivo JSON abaixo
        
        **Nota:** Certifique-se de que a Books API está habilitada no projeto.
        """)
        
        uploaded_json = st.file_uploader(
            "Upload do arquivo JSON de credenciais",
            type=['json'],
            help="Arquivo JSON da conta de serviço do Google Cloud"
        )
        
        if uploaded_json:
            try:
                service_account_data = json.load(uploaded_json)
                
                # Validar estrutura básica
                required_fields = ['type', 'project_id', 'private_key', 'client_email']
                if all(field in service_account_data for field in required_fields):
                    if service_account_data['type'] == 'service_account':
                        st.success(f"✅ Arquivo válido!")
                        st.info(f"📧 Conta: {service_account_data['client_email']}")
                        st.info(f"📋 Projeto: {service_account_data['project_id']}")
                        
                        if st.button("💾 Salvar Conta de Serviço", type="primary"):
                            st.session_state['service_account_json'] = service_account_data
                            st.session_state['google_api_key'] = ''  # Limpar chave API
                            st.success("✅ Conta de serviço configurada com sucesso!")
                            st.info("💡 As credenciais serão válidas durante esta sessão.")
                            st.warning("⚠️ Nota: Requer biblioteca PyJWT instalada. Se não estiver disponível, use Chave API.")
                    else:
                        st.error("❌ Arquivo inválido. Não é uma conta de serviço.")
                else:
                    st.error("❌ Arquivo JSON inválido. Campos obrigatórios ausentes.")
            except json.JSONDecodeError:
                st.error("❌ Erro ao ler arquivo JSON. Verifique se o arquivo está correto.")
        
        if st.button("🗑️ Remover Conta de Serviço"):
            st.session_state['service_account_json'] = None
            st.success("✅ Conta de serviço removida.")
    
    st.markdown("---")
    st.subheader("📊 Status de Autenticação")
    
    service_account = st.session_state.get('service_account_json', None)
    api_key = st.session_state.get('google_api_key', '')
    
    if service_account:
        st.success(f"✅ Conta de Serviço configurada: {service_account.get('client_email', 'N/A')}")
    elif api_key:
        st.success("✅ Chave API configurada")
    else:
        st.warning("⚠️ Usando quota gratuita (até 1000 requisições/dia)")
    
    st.markdown("---")
    st.subheader("📊 Status da Biblioteca")
    stats = obter_estatisticas()
    st.write(f"📚 Total de livros cadastrados: **{stats['total_livros']}**")

# Rodapé
st.sidebar.markdown("---")
st.sidebar.info("📚 Biblioteca de Livros PDF\n\nGerenciador de livros com SQLite")
