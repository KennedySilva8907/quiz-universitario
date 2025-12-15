import streamlit as st
import google.generativeai as genai
import pypdf
from pptx import Presentation
import docx2txt
import json
import re

# --- Configuração da Página ---
st.set_page_config(page_title="Gerador de Quizzes Universitário", page_icon="🎓", layout="centered")

st.title("🎓 Estuda com IA: Gerador de Quizzes")
st.write("Carrega os materiais da aula e personaliza o teu teste.")

# --- Barra Lateral para Configuração ---
with st.sidebar:
    st.header("⚙️ Configurações")
    
    # Campo de API Key (Vazio por segurança)
    api_key = st.text_input("Insere a tua API Key da Google", type="password")
    st.markdown("[Obter Chave Gratuita](https://aistudio.google.com/app/apikey)")
    
    st.divider() 
    
    # 1. Seletor de Modelo
    modelo_escolhido = st.selectbox(
        "Modelo da IA", 
        ["gemini-2.5-flash", "gemini-2.5-pro"],
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
        
        if not tipos_perguntas:
            st.warning("⚠️ Por favor seleciona pelo menos um tipo de pergunta na barra lateral.")
        
        elif st.button("🚀 Gerar Quiz Personalizado", type="primary"):
            with st.spinner("A IA está a gerar as perguntas..."):
                
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(modelo_escolhido)

                # --- PROMPT BLINDADO ---
                prompt = f"""
                Atua como um professor universitário. Cria um quiz baseado neste texto:
                "{texto_extraido[:30000]}"
                
                CONFIGURAÇÕES:
                - Quantidade: {qtd_perguntas} perguntas.
                - Dificuldade: {dificuldade}.
                - Foco: {tema_foco if tema_foco else "Geral"}.
                - Tipos permitidos: {', '.join(tipos_perguntas)}
                
                REGRAS DE FORMATAÇÃO ESTRITA:
                
                1. Múltipla Escolha: 
                   - {num_alternativas} opções.
                
                2. Verdadeiro/Falso: 
                   - Opções: ["A) Verdadeiro", "B) Falso"].
                
                3. Associação de Colunas (MUITO IMPORTANTE):
                   - No campo 'pergunta', tens de criar uma LISTA VERTICAL.
                   - Usa DUAS quebras de linha (\\n\\n) entre cada item numérico e cada item alfabético.
                   - Exemplo OBRIGATÓRIO para o campo 'pergunta':
                     "Associe os termos:\\n\\n1. Termo A\\n\\n2. Termo B\\n\\n--- Separador ---\\n\\nA. Definição X\\n\\nB. Definição Y"
                
                OUTPUT JSON OBRIGATÓRIO:
                Devolve APENAS um JSON válido:
                [
                    {{
                        "tipo": "...",
                        "pergunta": "Texto da pergunta formatado...",
                        "opcoes": ["A) ...", "B) ..."],
                        "resposta_correta": "A",
                        "explicacao": "..."
                    }}
                ]
                """
                
                try:
                    response = model.generate_content(
                        prompt, 
                        generation_config={"response_mime_type": "application/json"}
                    )
                    
                    texto_resposta = response.text.replace("```json", "").replace("```", "")
                    
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
        
        # --- TRUQUE DE FORMATAÇÃO (O "FIX" FINAL) ---
        texto_pergunta = q['pergunta']
        
        # Se for Associação, vamos forçar quebras de linha visualmente
        if "Associação" in tipo_label or "Associe" in texto_pergunta:
            # Substitui "A. " por "\n\nA. " se estiver colado, para garantir a lista
            # Regex procura por Letra maiúscula seguida de ponto e espaço, precedida de espaço ou nada
            texto_pergunta = texto_pergunta.replace(". ", ".<br>") # Quebra suave HTML
            texto_pergunta = texto_pergunta.replace("\n", "<br>")  # Garante que \n vira quebra HTML
        
        # Usamos unsafe_allow_html=True para garantir que os <br> funcionam se o Markdown falhar
        st.markdown(f"**{i+1}. {q['pergunta']}**") 
        # Nota: Mantive o markdown original acima, mas se quiseres forçar HTML usa:
        # st.markdown(f"**{i+1}.** <br>{texto_pergunta}", unsafe_allow_html=True)
        
        escolha = st.radio(
            "A tua resposta:", 
            q['opcoes'], 
            key=f"q_{i}", 
            index=None,
            label_visibility="collapsed"
        )
        
        if escolha:
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
    st.warning("👈 Insere a API Key na barra lateral para começar.")
