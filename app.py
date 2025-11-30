import streamlit as st
import google.generativeai as genai
import pypdf
from pptx import Presentation
import docx2txt
import json

# --- Configuração da Página ---
st.set_page_config(page_title="Gerador de Quizzes Universitário", page_icon="🎓")

st.title("🎓 Estuda com IA: Gerador de Quizzes")
st.write("Carrega os materiais da aula (PDF, PPTX, DOCX) e a IA cria um teste para ti.")

# --- Barra Lateral para Configuração ---
with st.sidebar:
    st.header("Configurações")
    api_key = st.text_input("Insere a tua API Key da Google Gemini", type="password")
    st.markdown("[Obter Chave Gratuita Aqui](https://aistudio.google.com/app/apikey)")
    
    # Seletor de modelo (caso o 2.5 falhe, podes mudar aqui)
    modelo_escolhido = st.selectbox(
        "Modelo da IA", 
        ["gemini-2.5-flash", "gemini-2.5-pro"],
        index=0
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
uploaded_file = st.file_uploader("Carrega o ficheiro da aula", type=['pdf', 'pptx', 'docx'])

if uploaded_file is not None and api_key:
    # 1. Extrair texto
    texto_extraido = ""
    try:
        if uploaded_file.name.endswith('.pdf'):
            texto_extraido = ler_pdf(uploaded_file)
        elif uploaded_file.name.endswith('.pptx'):
            texto_extraido = ler_pptx(uploaded_file)
        elif uploaded_file.name.endswith('.docx'):
            texto_extraido = ler_docx(uploaded_file)
        
        st.success(f"Ficheiro lido! ({len(texto_extraido)} caracteres encontrados)")
        
        # Botão para gerar
        if st.button("Gerar Quiz com Gemini"):
            with st.spinner("A IA está a ler a matéria e a criar as perguntas..."):
                
                # 2. Configurar Gemini
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(modelo_escolhido)

                # 3. O Prompt (Refinado para garantir formato)
                prompt = f"""
                Atua como um professor universitário. Com base neste texto de aula:
                "{texto_extraido[:30000]}"
                
                Gera um quiz com 10 perguntas de escolha múltipla.
                
                REGRAS ESTRITAS DE FORMATO:
                1. A resposta deve ser APENAS um JSON válido.
                2. As opções devem começar com a letra e parênteses, ex: "A) Resposta".
                3. A "resposta_correta" deve ser APENAS a letra maiúscula (ex: "A", "B", "C" ou "D").
                
                Estrutura do JSON:
                [
                    {{
                        "pergunta": "Texto da pergunta aqui?",
                        "opcoes": ["A) Opção 1", "B) Opção 2", "C) Opção 3", "D) Opção 4"],
                        "resposta_correta": "A",
                        "explicacao": "Explicação curta aqui."
                    }}
                ]
                """
                
                try:
                    # Configuração para forçar JSON (ajuda nos modelos novos)
                    generation_config = {"response_mime_type": "application/json"}
                    try:
                        response = model.generate_content(prompt, generation_config=generation_config)
                    except:
                        response = model.generate_content(prompt)

                    texto_bruto = response.text
                    
                    # --- LIMPEZA AVANÇADA DE JSON ---
                    inicio_json = texto_bruto.find('[')
                    fim_json = texto_bruto.rfind(']') + 1

                    if inicio_json != -1 and fim_json != 0:
                        texto_limpo = texto_bruto[inicio_json:fim_json]
                        st.session_state['quiz_data'] = json.loads(texto_limpo)
                        st.session_state['respostas'] = {} 
                        st.rerun()
                    else:
                        st.error("A IA respondeu, mas não encontrei o formato JSON correto.")
                        st.code(texto_bruto)

                except Exception as e:
                    st.error(f"Erro ao gerar: {e}")

    except Exception as e:
        st.error(f"Erro ao ler ficheiro: {e}")

# --- Mostrar o Quiz ---
if 'quiz_data' in st.session_state:
    st.markdown("---")
    st.subheader("📝 Responde agora:")
    
    respostas_certas = 0
    
    for i, q in enumerate(st.session_state['quiz_data']):
        st.markdown(f"**{i+1}. {q['pergunta']}**")
        
        # Guardar a escolha do utilizador
        escolha = st.radio(
            f"Opções {i}", 
            q['opcoes'], 
            key=f"q{i}", 
            index=None,
            label_visibility="collapsed"
        )
        
        if escolha:
            # --- CORREÇÃO DO ERRO AQUI ---
            # Extraímos apenas a primeira letra da escolha do utilizador (ex: "B) Texto" -> "B")
            letra_escolhida = escolha[0].upper() 
            letra_correta = q['resposta_correta'].strip().upper()
            
            if letra_escolhida == letra_correta:
                st.success(f"✅ Correto! {q['explicacao']}")
                respostas_certas += 1
            else:
                st.error(f"❌ Errado. A correta era: {q['resposta_correta']}")
                st.caption(f"Explicação: {q['explicacao']}")
        
        st.markdown("---")

    # Placar final (opcional)
    if len(st.session_state['quiz_data']) > 0:
        st.metric(label="Pontuação Atual", value=f"{respostas_certas} / {len(st.session_state['quiz_data'])}")

elif not api_key:
    st.warning("👈 Cola a tua API Key na barra lateral para começar.")
