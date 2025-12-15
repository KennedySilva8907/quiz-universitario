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

# --- Função para extrair letra da resposta ---
def extrair_letra(texto):
    """Extrai a letra da resposta (A, B, C, etc.) de forma robusta"""
    if not texto:
        return None
    
    # Remove espaços extras
    texto = str(texto).strip()
    
    # Se já for só uma letra
    if len(texto) == 1 and texto.isalpha():
        return texto.upper()
    
    # Se tiver formato "A)" ou "A) texto"
    match = re.match(r'^([A-Z])\)', texto)
    if match:
        return match.group(1).upper()
    
    # Se começar com letra seguida de qualquer coisa
    if texto[0].isalpha():
        return texto[0].upper()
    
    return None

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

                # --- PROMPT MELHORADO ---
                prompt = f"""
                Atua como um professor universitário experiente. Cria um quiz rigoroso baseado neste conteúdo:
                
                CONTEÚDO DO MATERIAL:
                "{texto_extraido[:30000]}"
                
                CONFIGURAÇÕES DO QUIZ:
                - Quantidade: {qtd_perguntas} perguntas
                - Dificuldade: {dificuldade}
                - Foco específico: {tema_foco if tema_foco else "Todos os tópicos do material"}
                - Tipos de perguntas: {', '.join(tipos_perguntas)}
                
                REGRAS OBRIGATÓRIAS:
                
                1. **Múltipla Escolha**:
                   - Cria {num_alternativas} opções no formato: "A) texto", "B) texto", etc.
                   - A resposta_correta deve ser APENAS a letra: "A", "B", "C", etc.
                   - Se a pergunta incluir código SQL, tabelas ou dados, INCLUI TUDO no campo 'pergunta'
                   - Exemplo de pergunta com SQL:
                     "Dadas as tabelas:\\n\\nEquipas: (idEquipa, nome)\\nJogadores: (id, nome, equipa_id)\\n\\nQual o resultado de:\\n```sql\\nSELECT * FROM Equipas\\n```"
                
                2. **Verdadeiro/Falso**:
                   - Opções: ["A) Verdadeiro", "B) Falso"]
                   - resposta_correta: "A" ou "B"
                
                3. **Associação de Colunas**:
                   - Formato da pergunta: "Associe os itens:\\n\\n1. Item Um\\n2. Item Dois\\n3. Item Três\\n\\n--- Separador ---\\n\\nA. Definição A\\nB. Definição B\\nC. Definição C"
                   - Opções: ["A) 1-A, 2-B, 3-C", "B) 1-B, 2-A, 3-C", ...]
                   - resposta_correta: apenas a letra da opção correta
                
                4. **IMPORTANTE SOBRE CONTEXTO**:
                   - Se a pergunta precisar de tabelas, dados de exemplo ou código para ser respondida, INCLUI TUDO no campo 'pergunta'
                   - Nunca assumas que o aluno tem acesso ao material original durante o teste
                   - Cada pergunta deve ser autocontida e completa
                
                5. **Formato da Explicação**:
                   - Deve ser clara e educativa
                   - Se for código/SQL, explica o que acontece passo a passo
                
                FORMATO JSON OBRIGATÓRIO (devolve APENAS isto, sem texto adicional):
                [
                    {{
                        "tipo": "Múltipla Escolha" ou "Verdadeiro ou Falso" ou "Associação de Colunas",
                        "pergunta": "Texto completo da pergunta com TODOS os dados necessários",
                        "opcoes": ["A) opção1", "B) opção2", ...],
                        "resposta_correta": "A",
                        "explicacao": "Explicação detalhada da resposta correta"
                    }}
                ]
                
                VALIDAÇÃO FINAL:
                - Verifica se todas as perguntas têm 'resposta_correta' como uma letra simples (A, B, C, etc.)
                - Verifica se todas as perguntas incluem TODOS os dados necessários para serem respondidas
                - Verifica se o JSON está válido e bem formatado
                """
                
                try:
                    response = model.generate_content(
                        prompt, 
                        generation_config={"response_mime_type": "application/json"}
                    )
                    
                    texto_resposta = response.text.replace("```json", "").replace("```", "").strip()
                    
                    inicio = texto_resposta.find('[')
                    fim = texto_resposta.rfind(']') + 1

                    if inicio != -1 and fim != 0:
                        json_str = texto_resposta[inicio:fim]
                        quiz_data = json.loads(json_str)
                        
                        # Validação e limpeza dos dados
                        quiz_limpo = []
                        for q in quiz_data:
                            # Garante que todos os campos existem
                            if all(key in q for key in ['tipo', 'pergunta', 'opcoes', 'resposta_correta', 'explicacao']):
                                # Limpa a resposta_correta para garantir que é só a letra
                                q['resposta_correta'] = extrair_letra(q['resposta_correta']) or "A"
                                quiz_limpo.append(q)
                        
                        if quiz_limpo:
                            st.session_state['quiz_data'] = quiz_limpo
                            
                            # Limpar estados antigos
                            for key in list(st.session_state.keys()):
                                if key.startswith('q_'):
                                    del st.session_state[key]
                            st.rerun()
                        else:
                            st.error("❌ Erro: Nenhuma pergunta válida foi gerada. Tenta novamente.")
                    else:
                        st.error("❌ Erro: A IA não devolveu um formato JSON válido. Tenta novamente.")

                except json.JSONDecodeError as e:
                    st.error(f"❌ Erro ao processar JSON: {e}")
                    with st.expander("Ver resposta da IA (debug)"):
                        st.code(texto_resposta)
                except Exception as e:
                    st.error(f"❌ Erro na API Google: {e}")

    except Exception as e:
        st.error(f"❌ Erro ao ler ficheiro: {e}")

# --- Mostrar o Quiz ---
if 'quiz_data' in st.session_state:
    st.markdown("---")
    st.subheader(f"📝 Quiz Gerado ({len(st.session_state['quiz_data'])} Perguntas)")
    
    respostas_certas = 0
    total = len(st.session_state['quiz_data'])
    
    for i, q in enumerate(st.session_state['quiz_data']):
        tipo_label = q.get('tipo', 'Pergunta')
        
        # Container para cada pergunta
        with st.container():
            st.markdown(f"### Pergunta {i+1}")
            st.caption(f"📌 Tipo: {tipo_label}")
            
            # Formatar a pergunta dependendo do tipo
            texto_pergunta = q['pergunta']
            
            # Detecta se tem código SQL ou blocos de código
            if '```' in texto_pergunta or 'SELECT' in texto_pergunta.upper() or 'FROM' in texto_pergunta.upper():
                # Separa texto normal de código
                partes = texto_pergunta.split('```')
                for idx, parte in enumerate(partes):
                    if idx % 2 == 0:
                        # Texto normal
                        st.markdown(parte)
                    else:
                        # Código
                        # Remove identificador de linguagem se houver (sql, python, etc)
                        codigo = re.sub(r'^(sql|python|java|javascript)\n', '', parte, flags=re.IGNORECASE)
                        st.code(codigo.strip(), language='sql')
            
            # Se for associação, formata em colunas
            elif "Associação" in tipo_label or "Associe" in texto_pergunta or "--- Separador ---" in texto_pergunta:
                if "--- Separador ---" in texto_pergunta:
                    partes = texto_pergunta.split("--- Separador ---")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Coluna 1:**")
                        st.markdown(partes[0].replace("\\n", "\n"))
                    with col2:
                        st.markdown("**Coluna 2:**")
                        st.markdown(partes[1].replace("\\n", "\n"))
                else:
                    st.markdown(texto_pergunta.replace("\\n", "\n"))
            else:
                # Pergunta normal
                st.markdown(texto_pergunta.replace("\\n", "\n"))
            
            # Opções de resposta
            escolha = st.radio(
                "Seleciona a tua resposta:", 
                q['opcoes'], 
                key=f"q_{i}", 
                index=None
            )
            
            # Verificação da resposta
            if escolha:
                letra_user = extrair_letra(escolha)
                letra_correta = extrair_letra(q.get('resposta_correta', ''))
                
                if letra_user and letra_correta and letra_user == letra_correta:
                    st.success(f"✅ **Correto!**")
                    st.info(f"💡 {q.get('explicacao', 'Sem explicação disponível.')}")
                    respostas_certas += 1
                elif letra_user and letra_correta:
                    st.error(f"❌ **Errado.** A resposta correta era: **{letra_correta}**")
                    st.info(f"💡 {q.get('explicacao', 'Sem explicação disponível.')}")
                else:
                    st.warning("⚠️ Erro ao processar a resposta. Por favor reporta este bug.")
            
            st.markdown("---")

    # Resultado final
    if total > 0:
        percentagem = (respostas_certas / total) * 100
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Respostas Certas", f"{respostas_certas}")
        with col2:
            st.metric("Total de Perguntas", f"{total}")
        with col3:
            st.metric("Percentagem", f"{percentagem:.1f}%")
        
        if respostas_certas == total:
            st.balloons()
            st.success("🎉 **Parabéns! Acertaste todas!**")
        elif percentagem >= 70:
            st.success("👏 **Bom trabalho!**")
        elif percentagem >= 50:
            st.info("📚 **Continua a estudar!**")
        else:
            st.warning("💪 **Não desistas! Revê a matéria e tenta novamente.**")

elif not api_key:
    st.warning("👈 Insere a API Key na barra lateral para começar.")
else:
    st.info("📤 Carrega um ficheiro (PDF, PPTX ou DOCX) para gerar o quiz.")

