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

# --- Função para formatar blocos SQL ---
def formatar_pergunta_sql(texto):
    """Formata perguntas que contêm código SQL de forma legível"""
    
    # Padrão 1: Blocos com ```sql ou ```
    if '```' in texto:
        partes = []
        blocos = texto.split('```')
        
        for idx, bloco in enumerate(blocos):
            if idx % 2 == 0:
                # Texto normal
                if bloco.strip():
                    partes.append(('texto', bloco.strip()))
            else:
                # Código
                codigo = re.sub(r'^(sql|python|java|javascript|c\+\+|c#)\s*\n', '', bloco, flags=re.IGNORECASE)
                partes.append(('codigo', codigo.strip()))
        
        return partes
    
    # Padrão 2: Blocos com palavras-chave SQL sem marcadores
    # Detecta CREATE, SELECT, INSERT, etc. e formata automaticamente
    sql_keywords = r'\b(CREATE|SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|FROM|WHERE|JOIN|GROUP BY|ORDER BY|HAVING)\b'
    
    if re.search(sql_keywords, texto, re.IGNORECASE):
        # Tenta separar texto descritivo de código SQL
        linhas = texto.split('\n')
        partes = []
        bloco_sql = []
        bloco_texto = []
        
        for linha in linhas:
            # Se a linha tem SQL keywords, é código
            if re.search(sql_keywords, linha, re.IGNORECASE):
                # Guarda texto acumulado
                if bloco_texto:
                    partes.append(('texto', '\n'.join(bloco_texto).strip()))
                    bloco_texto = []
                bloco_sql.append(linha)
            else:
                # Guarda SQL acumulado
                if bloco_sql:
                    partes.append(('codigo', '\n'.join(bloco_sql).strip()))
                    bloco_sql = []
                bloco_texto.append(linha)
        
        # Adiciona blocos finais
        if bloco_texto:
            partes.append(('texto', '\n'.join(bloco_texto).strip()))
        if bloco_sql:
            partes.append(('codigo', '\n'.join(bloco_sql).strip()))
        
        return partes if len(partes) > 1 else [('texto', texto)]
    
    # Sem SQL, retorna como texto normal
    return [('texto', texto)]

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

                # --- PROMPT CORRIGIDO (FORÇA O NÚMERO EXATO) ---
                prompt = f"""
                Atua como um professor universitário experiente. Cria um quiz rigoroso baseado neste conteúdo:
                
                CONTEÚDO DO MATERIAL:
                "{texto_extraido[:30000]}"
                
                ⚠️ CONFIGURAÇÕES OBRIGATÓRIAS DO QUIZ:
                - Quantidade: EXATAMENTE {qtd_perguntas} perguntas (nem mais, nem menos)
                - Dificuldade: {dificuldade}
                - Foco específico: {tema_foco if tema_foco else "Todos os tópicos do material"}
                - Tipos de perguntas permitidos: {', '.join(tipos_perguntas)}
                
                📋 REGRAS DE FORMATAÇÃO:
                
                1. **Múltipla Escolha**:
                   - {num_alternativas} opções no formato: "A) texto", "B) texto", etc.
                   - resposta_correta: APENAS a letra (ex: "A")
                   
                2. **Verdadeiro/Falso**:
                   - Opções: ["A) Verdadeiro", "B) Falso"]
                   - resposta_correta: "A" ou "B"
                
                3. **Associação de Colunas**:
                   - Formato: "Associe:\\n\\n1. Item\\n2. Item\\n\\n--- Separador ---\\n\\nA. Definição\\nB. Definição"
                   - Opções com combinações possíveis
                   - resposta_correta: letra da combinação correta
                
                🔴 REGRA CRÍTICA PARA CÓDIGO SQL/PROGRAMAÇÃO:
                - Coloca TODO o código SQL entre marcadores ```sql e ```
                - Exemplo correto:
                  "Considere a tabela:\\n\\n```sql\\nCREATE TABLE Equipas (...)\\n```\\n\\nQual o resultado?"
                - NUNCA mistures código SQL com texto sem os marcadores ```
                
                📊 IMPORTANTE SOBRE CONTEXTO:
                - Cada pergunta deve ser AUTOCONTIDA
                - Se precisar de tabelas/dados/código, INCLUI TUDO no campo 'pergunta'
                - O aluno NÃO tem acesso ao material durante o teste
                - Usa \\n para quebras de linha dentro do JSON
                
                ✅ VALIDAÇÃO OBRIGATÓRIA ANTES DE RESPONDER:
                1. Conta as perguntas: devem ser EXATAMENTE {qtd_perguntas}
                2. Verifica se cada 'resposta_correta' é uma letra simples (A, B, C...)
                3. Verifica se todo código SQL está entre ```sql e ```
                4. Verifica se o JSON é válido
                
                FORMATO JSON (retorna APENAS isto):
                [
                    {{
                        "tipo": "Múltipla Escolha",
                        "pergunta": "Texto com código formatado:\\n\\n```sql\\nSELECT * FROM tabela\\n```\\n\\nO que retorna?",
                        "opcoes": ["A) opção1", "B) opção2", "C) opção3", "D) opção4"],
                        "resposta_correta": "A",
                        "explicacao": "Explicação detalhada"
                    }}
                ]
                
                ⚠️ LEMBRA-TE: Devolve EXATAMENTE {qtd_perguntas} perguntas no array JSON!
                """
                
                try:
                    response = model.generate_content(
                        prompt,
                        generation_config={
                            "response_mime_type": "application/json",
                            "temperature": 0.7,  # Criatividade moderada
                        }
                    )
                    
                    texto_resposta = response.text.replace("```json", "").replace("```", "").strip()
                    
                    inicio = texto_resposta.find('[')
                    fim = texto_resposta.rfind(']') + 1

                    if inicio != -1 and fim != 0:
                        json_str = texto_resposta[inicio:fim]
                        quiz_data = json.loads(json_str)
                        
                        # ✅ VALIDAÇÃO E CORREÇÃO DO NÚMERO DE PERGUNTAS
                        if len(quiz_data) > qtd_perguntas:
                            quiz_data = quiz_data[:qtd_perguntas]
                            st.warning(f"⚠️ A IA gerou {len(quiz_data)} perguntas. Foram cortadas para {qtd_perguntas}.")
                        elif len(quiz_data) < qtd_perguntas:
                            st.warning(f"⚠️ A IA gerou apenas {len(quiz_data)} perguntas (pediste {qtd_perguntas}). Tenta novamente ou reduz o número.")
                        
                        # Validação e limpeza dos dados
                        quiz_limpo = []
                        for q in quiz_data:
                            # Garante que todos os campos existem
                            if all(key in q for key in ['tipo', 'pergunta', 'opcoes', 'resposta_correta', 'explicacao']):
                                # Limpa a resposta_correta
                                q['resposta_correta'] = extrair_letra(q['resposta_correta']) or "A"
                                
                                # Garante que opcoes é uma lista
                                if not isinstance(q['opcoes'], list):
                                    continue
                                
                                quiz_limpo.append(q)
                        
                        if quiz_limpo:
                            st.session_state['quiz_data'] = quiz_limpo
                            
                            # Limpar estados antigos
                            for key in list(st.session_state.keys()):
                                if key.startswith('q_') or key.startswith('respondido_'):
                                    del st.session_state[key]
                            
                            st.success(f"✅ Quiz gerado com {len(quiz_limpo)} perguntas!")
                            st.rerun()
                        else:
                            st.error("❌ Nenhuma pergunta válida foi gerada. Tenta novamente.")
                    else:
                        st.error("❌ A IA não devolveu JSON válido. Tenta novamente.")

                except json.JSONDecodeError as e:
                    st.error(f"❌ Erro ao processar JSON: {e}")
                    with st.expander("🔍 Ver resposta da IA (debug)"):
                        st.code(texto_resposta)
                except Exception as e:
                    st.error(f"❌ Erro na API: {e}")

    except Exception as e:
        st.error(f"❌ Erro ao ler ficheiro: {e}")

# --- MOSTRAR O QUIZ (FORMATAÇÃO CORRIGIDA) ---
if 'quiz_data' in st.session_state:
    st.markdown("---")
    st.subheader(f"📝 Quiz Gerado ({len(st.session_state['quiz_data'])} Perguntas)")
    
    respostas_certas = 0
    respostas_dadas = 0
    total = len(st.session_state['quiz_data'])
    
    for i, q in enumerate(st.session_state['quiz_data']):
        tipo_label = q.get('tipo', 'Pergunta')
        
        # Container para cada pergunta
        with st.container():
            st.markdown(f"### 📌 Pergunta {i+1} de {total}")
            st.caption(f"Tipo: {tipo_label}")
            
            # --- FORMATAÇÃO MELHORADA ---
            texto_pergunta = q['pergunta']
            
            # 🔧 CORREÇÃO: Formata SQL automaticamente
            if "Associação" in tipo_label or "Associe" in texto_pergunta:
                # Perguntas de associação
                if "--- Separador ---" in texto_pergunta:
                    partes = texto_pergunta.split("--- Separador ---")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Coluna 1:**")
                        # Processa cada coluna separadamente
                        for parte_col1 in formatar_pergunta_sql(partes[0]):
                            if parte_col1[0] == 'codigo':
                                st.code(parte_col1[1], language='sql')
                            else:
                                st.markdown(parte_col1[1])
                    with col2:
                        st.markdown("**Coluna 2:**")
                        for parte_col2 in formatar_pergunta_sql(partes[1]):
                            if parte_col2[0] == 'codigo':
                                st.code(parte_col2[1], language='sql')
                            else:
                                st.markdown(parte_col2[1])
                else:
                    st.markdown(texto_pergunta.replace("\\n", "\n"))
            else:
                # Perguntas normais ou com SQL
                partes_formatadas = formatar_pergunta_sql(texto_pergunta)
                
                for tipo_parte, conteudo in partes_formatadas:
                    if tipo_parte == 'codigo':
                        st.code(conteudo, language='sql')
                    else:
                        st.markdown(conteudo)
            
            # Opções de resposta
            escolha = st.radio(
                "Seleciona a tua resposta:", 
                q['opcoes'], 
                key=f"q_{i}", 
                index=None
            )
            
            # Verificação da resposta
            if escolha:
                # Marca como respondida
                if f'respondido_{i}' not in st.session_state:
                    st.session_state[f'respondido_{i}'] = True
                
                letra_user = extrair_letra(escolha)
                letra_correta = extrair_letra(q.get('resposta_correta', ''))
                
                if letra_user and letra_correta:
                    if letra_user == letra_correta:
                        st.success(f"✅ **Correto!**")
                        st.info(f"💡 **Explicação:** {q.get('explicacao', 'Sem explicação.')}")
                        respostas_certas += 1
                    else:
                        st.error(f"❌ **Errado.** A resposta correta era: **{letra_correta})**")
                        st.info(f"💡 **Explicação:** {q.get('explicacao', 'Sem explicação.')}")
                    
                    respostas_dadas += 1
                else:
                    st.warning("⚠️ Erro ao processar resposta.")
            
            st.markdown("---")

    # Resultado final
    if total > 0:
        percentagem = (respostas_certas / total) * 100 if respostas_dadas == total else 0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("✅ Certas", f"{respostas_certas}/{total}")
        with col2:
            st.metric("📊 Percentagem", f"{percentagem:.0f}%")
        with col3:
            if respostas_dadas == total:
                if percentagem >= 70:
                    st.metric("🎯 Resultado", "Aprovado")
                else:
                    st.metric("📚 Resultado", "Estuda Mais")
        
        if respostas_dadas == total:
            if respostas_certas == total:
                st.balloons()
                st.success("🎉 **PERFEITO! Acertaste todas!**")
            elif percentagem >= 70:
                st.success("👏 **Bom trabalho! Passaste!**")
            elif percentagem >= 50:
                st.info("📚 **Razoável. Revê alguns tópicos.**")
            else:
                st.warning("💪 **Continua a estudar! Vais conseguir!**")

elif not api_key:
    st.warning("👈 Insere a API Key na barra lateral para começar.")
else:
    st.info("📤 Carrega um ficheiro (PDF, PPTX ou DOCX) para gerar o quiz.")

