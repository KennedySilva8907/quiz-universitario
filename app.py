import streamlit as st
import google.generativeai as genai
import pypdf
from pptx import Presentation
import docx2txt
import json

# --- Configuração da Página ---
st.set_page_config(page_title="Gerador de Quizzes Universitário", page_icon="🎓", layout="centered")

st.title("🎓 Estuda com IA: Gerador de Quizzes (Gemini)")
st.write("Carrega os materiais da aula e personaliza o teu teste.")

# --- Barra Lateral para Configuração ---
with st.sidebar:
    st.header("⚙️ Configurações")
    
    # A tua chave NOVA já está aqui
    default_key = "AIzaSyDGMdOBaAIUrE827c9UhHNZLx44N-7iPJg"
    api_key = st.text_input("Insere a tua API Key da Google", value=default_key, type="password")
    st.markdown("[Obter Chave Gratuita](https://aistudio.google.com/app/apikey)")
    
    st.divider() 
    
    # 1. Seletor de Modelo (Atualizado para as versões estáveis 1.5)
    modelo_escolhido = st.selectbox(
        "Modelo da IA", 
        ["gemini-1.5-flash", "gemini-1.5-pro"],
        index=0
    )
    
    # 2. Nível de Dificuldade
    dificuldade = st.selectbox(
        "Nível de Dificuldade",
        ["Fácil (Memorização)", "Médio (Aplicação)", "Difícil (Análise Crítica)"],
        index=1
    )
    
    # 3. Tipos de Perguntas
    tipos_perguntas = st.multiselect(
        "Tipos de Perguntas (Seleciona pelo menos um)",
        ["Múltipla Escolha", "Verdadeiro ou Falso", "Associação de Colunas"],
        default=["Múltipla Escolha", "Verdadeiro ou Falso"]
    )
    
    # 4. Quantidade de Perguntas
    qtd_perguntas = st.slider("Número de Perguntas", 3, 20, 5)

    # 5. Número de Alternativas
    num_alternativas = st.slider(
        "Opções (apenas para Múltipla Escolha)",
        3, 6, 4
    )

# --- Funções de Leitura de Ficheiros ---
def ler_pdf(file):
    pdf_reader = pypdf.PdfReader(file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() or ""
    return text

def ler_pptx(file):
    prs = Presentation(file)
    text = ""
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text += shape.text + "\n"
    return text

def ler_docx(file):
    return docx2txt.process(file)

# --- Lógica Principal ---
st.subheader("1. Carregar Material")
uploaded_file = st.file_uploader("Arrasta o teu ficheiro aqui", type=['pdf', 'pptx', 'docx'])

tema_foco = st.text_input(
    "Queres focar num tema específico? (Opcional)",
    placeholder="Ex: Foca-te apenas nas datas históricas"
)

if uploaded_file is not None and api_key:
    # Extrair texto
    texto_extraido = ""
    try:
        if uploaded_file.name.endswith('.pdf'):
            texto_extraido = ler_pdf(uploaded_file)
        elif uploaded_file.name.endswith('.pptx'):
            texto_extraido = ler_pptx(uploaded_file)
        elif uploaded_file.name.endswith('.docx'):
            texto_extraido = ler_docx(uploaded_file)
        
        st.info(f"📄 Ficheiro carregado! ({len(texto_extraido)} caracteres)")
        
        if not tipos_perguntas:
            st.warning("⚠️ Por favor seleciona pelo menos um tipo de pergunta na barra lateral.")
        
        elif st.button("🚀 Gerar Quiz Personalizado", type="primary"):
            with st.spinner("A IA está a pensar... (Isto pode demorar uns segundos)"):
                
                # Configurar Gemini
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(modelo_escolhido)

                # --- PROMPT ---
                prompt = f"""
                Atua como um professor universitário. Cria um quiz baseado neste texto:
                "{texto_extraido[:30000]}"
                
                CONFIGURAÇÕES:
                - Quantidade: {qtd_perguntas} perguntas.
                - Dificuldade: {dificuldade}.
                - Foco: {tema_foco if tema_foco else "Geral"}.
                - Tipos permitidos: {', '.join(tipos_perguntas)}
                
                REGRAS DE FORMATAÇÃO:
                1. Múltipla Escolha: {num_alternativas} opções (A, B, C...).
                2. Verdadeiro/Falso: Opções ["A) Verdadeiro", "B) Falso"].
                3. Associação: Pergunta com itens, Opções com sequências corretas.
                
                OUTPUT JSON OBRIGATÓRIO:
                Devolve APENAS um JSON válido (sem markdown, sem ```json):
                [
                    {{
                        "tipo": "Múltipla Escolha",
                        "pergunta": "...",
                        "opcoes": ["A) ...", "B) ..."],
                        "resposta_correta": "A",
                        "explicacao": "..."
                    }}
                ]
                """
                
                try:
                    # Tenta forçar JSON mode (funciona nas versões mais recentes)
                    response = model.generate_content(
                        prompt, 
                        generation_config={"response_mime_type": "application/json"}
                    )
                    
                    texto_resposta = response.text
                    
                    # Limpeza extra caso o modelo ponha Markdown
                    texto_resposta = texto_resposta.replace("```json", "").replace("```", "")
                    
                    # Encontrar o início e fim da lista JSON
                    inicio = texto_resposta.find('[')
                    fim = texto_resposta.rfind(']') + 1

                    if inicio != -1 and fim != 0:
                        json_str = texto_resposta[inicio:fim]
                        st.session_state['quiz_data'] = json.loads(json_str)
                        
                        # Limpar estados antigos
                        for key in list(st.session_state.keys()):
                            if key.startswith('q_'):
                                del st.session_state[key]
                        st.rerun()
                    else:
                        st.error("Erro: A IA não devolveu um formato válido. Tenta novamente.")

                except Exception as e:
                    st.error(f"Erro na API Google: {e}")

    except Exception as e:
        st.error(f"Erro ao ler ficheiro: {e}")

# --- Mostrar o Quiz ---
if 'quiz_data' in st.session_state:
    st.markdown("---")
    st.subheader(f"📝 Quiz Gerado ({len(st.session_state['quiz_data'])} Perguntas)")
    
    respostas_certas = 0
    total = len(st.session_state['quiz_data'])
    
    for i, q in enumerate(st.session_state['quiz_data']):
        tipo_label = q.get('tipo', 'Pergunta')
        st.caption(f"📌 {tipo_label}")
        
        st.markdown(f"**{i+1}. {q['pergunta']}**")
        
        escolha = st.radio(
            "A tua resposta:", 
            q['opcoes'], 
            key=f"q_{i}", 
            index=None,
            label_visibility="collapsed"
        )
        
        if escolha:
            # Extração da letra (robusta)
            letra_user = escolha.split(')')[0].strip().upper() if ')' in escolha else escolha[0].upper()
            letra_correta = q['resposta_correta'].split(')')[0].strip().upper() if ')' in q['resposta_correta'] else q['resposta_correta'].strip().upper()
            
            if letra_user == letra_correta:
                st.success(f"✅ Correto! {q['explicacao']}")
                respostas_certas += 1
            else:
                st.error(f"❌ Errado. A correta era {letra_correta}.")
                st.caption(f"Explicação: {q['explicacao']}")
        
        st.markdown("---")

    if total > 0:
        st.metric("Resultado Final", f"{respostas_certas} / {total}")
        if respostas_certas == total:
            st.balloons()

elif not api_key:
    st.warning("👈 Insere a API Key na barra lateral.")
