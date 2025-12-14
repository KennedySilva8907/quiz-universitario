import streamlit as st
from groq import Groq
import pypdf
from pptx import Presentation
import docx2txt
import json

# --- Configuração da Página ---
st.set_page_config(page_title="Gerador de Quizzes Universitário", page_icon="🎓", layout="centered")

st.title("🎓 Estuda com IA: Gerador de Quizzes (Groq)")
st.write("Carrega os materiais da aula e personaliza o teu teste.")

# --- Barra Lateral para Configuração ---
with st.sidebar:
    st.header("⚙️ Configurações")
    
    # A tua chave já está aqui pré-preenchida
    default_key = "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"
    api_key = st.text_input("Insere a tua API Key da Groq", value=default_key, type="password")
    st.markdown("[Obter Chave Gratuita](https://console.groq.com/keys)")
    
    st.divider() 
    
    # 1. Seletor de Modelo (Modelos rápidos da Groq)
    modelo_escolhido = st.selectbox(
        "Modelo da IA", 
        ["llama-3.3-70b-versatile", "llama3-70b-8192", "mixtral-8x7b-32768"],
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
        "Tipos de Perguntas",
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
        
        # Validação
        if not tipos_perguntas:
            st.warning("⚠️ Por favor seleciona pelo menos um tipo de pergunta na barra lateral.")
        
        elif st.button("🚀 Gerar Quiz Personalizado", type="primary"):
            with st.spinner("A IA está a criar perguntas variadas via Groq..."):
                
                # Inicializar Cliente Groq
                client = Groq(api_key=api_key)

                # --- PROMPT INTELIGENTE ---
                prompt_sistema = f"""
                Atua como um professor universitário. Vais receber um texto e deves criar um quiz.
                
                CONFIGURAÇÕES:
                - Quantidade: {qtd_perguntas} perguntas.
                - Dificuldade: {dificuldade}.
                - Foco: {tema_foco if tema_foco else "Geral"}.
                - Tipos permitidos: {', '.join(tipos_perguntas)}
                
                REGRAS DE FORMATAÇÃO:
                1. Múltipla Escolha: {num_alternativas} opções.
                2. Verdadeiro/Falso: Opções ["A) Verdadeiro", "B) Falso"].
                3. Associação: Pergunta com itens, Opções com sequências.
                
                OUTPUT JSON OBRIGATÓRIO:
                Retorna APENAS um JSON com esta estrutura exata:
                {{
                    "quiz": [
                        {{
                            "tipo": "...",
                            "pergunta": "...",
                            "opcoes": ["A) ...", "B) ..."],
                            "resposta_correta": "A",
                            "explicacao": "..."
                        }}
                    ]
                }}
                """
                
                # Limite de caracteres seguro para o Llama 3
                prompt_usuario = f"Texto base para o quiz: {texto_extraido[:30000]}" 
                
                try:
                    completion = client.chat.completions.create(
                        model=modelo_escolhido,
                        messages=[
                            {"role": "system", "content": prompt_sistema},
                            {"role": "user", "content": prompt_usuario}
                        ],
                        temperature=0.5,
                        # IMPORTANTE: Força a resposta em JSON (funcionalidade nativa da Groq)
                        response_format={"type": "json_object"}
                    )

                    # Processar resposta
                    texto_resposta = completion.choices[0].message.content
                    dados_json = json.loads(texto_resposta)
                    
                    # Garantir que apanhamos a lista correta
                    if "quiz" in dados_json:
                        lista_perguntas = dados_json["quiz"]
                    else:
                        # Tenta encontrar a primeira lista disponível no JSON caso a chave mude
                        lista_perguntas = next((v for v in dados_json.values() if isinstance(v, list)), None)

                    if lista_perguntas:
                        st.session_state['quiz_data'] = lista_perguntas
                        
                        # Limpar respostas antigas da sessão
                        for key in list(st.session_state.keys()):
                            if key.startswith('q_'):
                                del st.session_state[key]
                        st.rerun()
                    else:
                        st.error("O formato JSON recebido não contém uma lista de perguntas válida.")

                except Exception as e:
                    st.error(f"Erro na API Groq: {e}")

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
            # Lógica robusta para extrair a letra (A, B, C...)
            # Funciona mesmo que a IA mande "A) Texto" ou só "A"
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
    st.warning("👈 A API Key deve estar preenchida na barra lateral.")
