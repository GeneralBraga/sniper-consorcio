
import streamlit as st
import pandas as pd
import re
import itertools
from io import BytesIO
from fpdf import FPDF
from datetime import datetime
import os

# --- CONFIGURAÇÃO INICIAL (ÍCONE E TÍTULO) ---
# Tenta usar a logo como ícone da aba se ela existir
page_icon = "logo.png" if os.path.exists("logo.png") else "🏛️"

st.set_page_config(
    page_title="JBS CONTEMPLADAS",
    page_icon=page_icon,
    layout="wide"
)

# --- CORES DA MARCA ---
COLOR_GOLD = "#84754e"
COLOR_BEIGE = "#ecece4"
COLOR_BG = "#0e1117"

# --- CSS PERSONALIZADO ---
st.markdown(f"""
<style>
    .stApp {{background-color: {COLOR_BG}; color: {COLOR_BEIGE};}}
    .stButton>button {{
        width: 100%; 
        background-color: {COLOR_GOLD}; 
        color: white; 
        border: none; 
        border-radius: 6px; 
        font-weight: bold; 
        text-transform: uppercase;
        padding: 10px;
    }}
    .stButton>button:hover {{
        background-color: #6b5e3d; 
        color: {COLOR_BEIGE};
    }}
    h1, h2, h3 {{color: {COLOR_GOLD} !important; font-family: 'Helvetica', sans-serif;}}
    .stTextInput>div>div>input, .stNumberInput>div>div>input {{
        background-color: #1c1f26; 
        color: white; 
        border: 1px solid {COLOR_GOLD};
    }}
    /* Ajuste da Tabela */
    div[data-testid="stDataFrame"] {{
        border: 1px solid {COLOR_GOLD};
    }}
</style>
""", unsafe_allow_html=True)

# --- CABEÇALHO ---
c1, c2 = st.columns([1, 4])
with c1:
    if os.path.exists("logo.png"):
        st.image("logo.png", width=250) # Aumentei a logo
    else:
        st.markdown(f"<h1 style='color:{COLOR_GOLD}'>JBS</h1>", unsafe_allow_html=True)
with c2:
    st.markdown(f"<h1 style='margin-top: 20px;'>SISTEMA DE OPORTUNIDADES</h1>", unsafe_allow_html=True)
    st.markdown(f"**JBS Contempladas Consórcios** | Ferramenta Exclusiva")

st.markdown(f"<hr style='border: 1px solid {COLOR_GOLD}'>", unsafe_allow_html=True)

# --- FUNÇÕES ---
def limpar_moeda(texto):
    if not texto: return 0.0
    texto = str(texto).lower().strip().replace('\xa0', '').replace('&nbsp;', '')
    texto = re.sub(r'[^\d\.,]', '', texto)
    if not texto: return 0.0
    try:
        if ',' in texto and '.' in texto: return float(texto.replace('.', '').replace(',', '.'))
        elif ',' in texto: return float(texto.replace(',', '.'))
        elif '.' in texto:
             if len(texto.split('.')[1]) == 2: return float(texto)
             return float(texto.replace('.', ''))
        return float(texto)
    except: return 0.0

def extrair_dados_universal(texto_copiado):
    lista_cotas = []
    texto_limpo = "\n".join([line.strip() for line in texto_copiado.split('\n') if line.strip()])
    blocos = re.split(r'(?i)(?=imóvel|imovel|automóvel|automovel|veículo)', texto_limpo)
    if len(blocos) < 2: blocos = texto_limpo.split('\n\n')

    id_cota = 1
    for bloco in blocos:
        if len(bloco) < 20: continue
        bloco_lower = bloco.lower()
        
        admins = ['BRADESCO', 'SANTANDER', 'ITAÚ', 'ITAU', 'PORTO', 'CAIXA', 'BANCO DO BRASIL', 'BB', 'RODOBENS', 'EMBRACON', 'ANCORA', 'ÂNCORA', 'MYCON', 'SICREDI', 'SICOOB', 'MAPFRE', 'HS', 'YAMAHA', 'ZEMA', 'BANCORBRÁS', 'BANCORBRAS', 'SERVOPA']
        admin_encontrada = "OUTROS"
        for adm in admins:
            if adm.lower() in bloco_lower:
                admin_encontrada = adm.upper()
                break
        
        if admin_encontrada == "OUTROS" and "r$" not in bloco_lower: continue

        credito = 0.0
        match_cred = re.search(r'(?:crédito|credito|bem|valor)[^\d\n]*?R\$\s?([\d\.,]+)', bloco_lower)
        if match_cred: credito = limpar_moeda(match_cred.group(1))
        else:
            valores = re.findall(r'R\$\s?([\d\.,]+)', bloco)
            vals = sorted([limpar_moeda(v) for v in valores], reverse=True)
            if vals: credito = vals[0]

        entrada = 0.0
        match_ent = re.search(r'(?:entrada|ágio|agio|quero|pago)[^\d\n]*?R\$\s?([\d\.,]+)', bloco_lower)
        if match_ent: entrada = limpar_moeda(match_ent.group(1))
        else:
            valores = re.findall(r'R\$\s?([\d\.,]+)', bloco)
            vals = sorted([limpar_moeda(v) for v in valores], reverse=True)
            if len(vals) > 1: entrada = vals[1]

        regex_parc = r'(\d+)\s*[xX]\s*R?\$\s?([\d\.,]+)'
        todas_parcelas = re.findall(regex_parc, bloco)
        
        saldo_devedor = 0.0
        parcela_teto = 0.0
        for pz_str, vlr_str in todas_parcelas:
            pz = int(pz_str)
            vlr = limpar_moeda(vlr_str)
            saldo_devedor += (pz * vlr)
            if pz > 1 and vlr > parcela_teto: parcela_teto = vlr
            elif len(todas_parcelas) == 1: parcela_teto = vlr

        if credito > 0 and entrada > 0:
            if saldo_devedor == 0: saldo_devedor = (credito * 1.3) - entrada
            custo_total = entrada + saldo_devedor
            if credito > 5000: 
                lista_cotas.append({
                    'ID': id_cota, 'Admin': admin_encontrada, 'Crédito': credito, 'Entrada': entrada,
                    'Parcela': parcela_teto, 'Saldo': saldo_devedor, 'CustoTotal': custo_total,
                    'EntradaPct': (entrada/credito) if credito else 0
                })
                id_cota += 1
    return lista_cotas

def processar_combinacoes(cotas, min_cred, max_cred, max_ent, max_parc, max_custo):
    combinacoes_validas = []
    cotas_por_admin = {}
    for cota in cotas:
        adm = cota['Admin']
        if adm not in cotas_por_admin: cotas_por_admin[adm] = []
        cotas_por_admin[adm].append(cota)
    
    progress_bar = st.progress(0)
    total_admins = len(cotas_por_admin)
    current = 0

    for admin, grupo in cotas_por_admin.items():
        if admin == "OUTROS": continue
        current += 1
        progress_bar.progress(int((current / total_admins) * 100))
        grupo.sort(key=lambda x: x['EntradaPct'])
        
        count = 0
        max_ops = 2000000 
        
        for r in range(1, 7):
            iterator = itertools.combinations(grupo, r)
            while True:
                try:
                    combo = next(iterator)
                    count += 1
                    if count > max_ops: break
                    
                    soma_ent = sum(c['Entrada'] for c in combo)
                    if soma_ent > (max_ent * 1.05): continue
                    soma_cred = sum(c['Crédito'] for c in combo)
                    if soma_cred < min_cred or soma_cred > max_cred: continue
                    soma_parc = sum(c['Parcela'] for c in combo)
                    if soma_parc > (max_parc * 1.05): continue
                    soma_custo = sum(c['CustoTotal'] for c in combo)
                    custo_real = (soma_custo / soma_cred) - 1
                    if custo_real > max_custo: continue
                    
                    ids = " + ".join([str(c['ID']) for c in combo])
                    detalhes = " || ".join([f"[ID {c['ID']}] Cr: R$ {c['Crédito']:,.0f}" for c in combo])
                    
                    status = "⚠️ PADRÃO"
                    if custo_real <= 0.20: status = "💎 OURO"
                    elif custo_real <= 0.35: status = "🔥 IMPERDÍVEL"
                    elif custo_real <= 0.45: status = "✨ EXCELENTE"
                    elif custo_real <= 0.50: status = "✅ OPORTUNIDADE"
                    
                    combinacoes_validas.append({
                        'Admin': admin, 'Status': status, 'IDs': ids,
                        'Crédito Total': soma_cred, 'Entrada Total': soma_ent,
                        'Parcela Total': soma_parc, 
                        'Custo Real (%)': custo_real, # Mantém decimal para cálculo (0.44)
                        'Detalhes': detalhes
                    })
                    if len([x for x in combinacoes_validas if x['Admin'] == admin]) > 150: break
                except StopIteration: break
            if count > max_ops: break
    progress_bar.empty()
    return pd.DataFrame(combinacoes_validas)

# --- PDF CUSTOMIZADO ---
class PDF(FPDF):
    def header(self):
        # Logo no PDF
        if os.path.exists("logo.png"):
            # x=10, y=8, w=33 (ajuste conforme necessário)
            self.image('logo.png', 10, 6, 30)
        
        # Fundo do cabeçalho Dourado
        self.set_fill_color(132, 117, 78) # #84754e
        # Desenha retângulo (começando um pouco depois da logo para não cobrir se não for transparente)
        # Se a logo for transparente, pode desenhar por baixo.
        # Aqui, desenhamos o fundo no topo
        self.rect(0, 0, 297, 25, 'F') 
        
        # Se tiver logo, a gente recoloca ela por cima do fundo (se for PNG transparente)
        if os.path.exists("logo.png"):
            self.image('logo.png', 10, 5, 40)

        self.set_font('Arial', 'B', 16)
        self.set_text_color(255, 255, 255)
        # Texto centralizado compensando a logo
        self.cell(0, 15, 'RELATÓRIO DE OPORTUNIDADES', 0, 1, 'C')
        self.ln(10)

def limpar_emojis(texto):
    # Remove caracteres fora do padrão ASCII/Latin-1 para não quebrar o PDF
    return texto.encode('latin-1', 'ignore').decode('latin-1')

def gerar_pdf_final(df):
    pdf = PDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", size=9)
    
    # Cabeçalho da Tabela
    pdf.set_fill_color(236, 236, 228) # Bege
    pdf.set_text_color(0)
    pdf.set_font("Arial", 'B', 9)
    
    headers = ["Admin", "Status", "Credito", "Entrada", "Parcela", "Custo", "Detalhes"]
    w = [30, 35, 35, 35, 30, 20, 90]
    
    for i, h in enumerate(headers):
        pdf.cell(w[i], 10, h, 1, 0, 'C', True)
    pdf.ln()
    
    # Linhas
    pdf.set_font("Arial", size=8)
    for index, row in df.iterrows():
        # Limpa emojis do status
        status_clean = limpar_emojis(row['Status'])
        # Remove emojis como 💎 e 🔥 e deixa só texto
        status_clean = status_clean.replace("?", "").strip() 
        
        pdf.cell(w[0], 8, limpar_emojis(str(row['Admin'])), 1, 0, 'C')
        pdf.cell(w[1], 8, status_clean, 1, 0, 'C')
        pdf.cell(w[2], 8, f"R$ {row['Crédito Total']:,.2f}", 1, 0, 'R')
        pdf.cell(w[3], 8, f"R$ {row['Entrada Total']:,.2f}", 1, 0, 'R')
        pdf.cell(w[4], 8, f"R$ {row['Parcela Total']:,.2f}", 1, 0, 'R')
        pdf.cell(w[5], 8, f"{row['Custo Real (%)']*100:.2f}%", 1, 0, 'C')
        
        detalhe = limpar_emojis(row['Detalhes'])
        pdf.cell(w[6], 8, detalhe[:55], 1, 1, 'L')
        
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- INTERFACE PRINCIPAL ---

# Inicializa Session State para os dados
if 'df_resultado' not in st.session_state:
    st.session_state.df_resultado = None

with st.expander("📋 DADOS DO SITE (Colar aqui)", expanded=True):
    texto_site = st.text_area("", height=100, key="input_texto")

st.subheader("Filtros JBS")
c1, c2 = st.columns(2)
# Formatação no input visual
min_c = c1.number_input("Crédito Mín (R$)", 640000.0, step=10000.0, format="%.2f")
max_c = c1.number_input("Crédito Máx (R$)", 710000.0, step=10000.0, format="%.2f")
max_e = c2.number_input("Entrada Máx (R$)", 280000.0, step=5000.0, format="%.2f")
max_p = c2.number_input("Parcela Máx (R$)", 4500.0, step=100.0, format="%.2f")
max_k = st.slider("Custo Máx (%)", 0.0, 1.0, 0.55, 0.01)

# BOTÃO DE PROCESSAR
if st.button("🔍 LOCALIZAR OPORTUNIDADES"):
    if texto_site:
        cotas = extrair_dados_universal(texto_site)
        if cotas:
            # Processa e SALVA NO SESSION STATE
            st.session_state.df_resultado = processar_combinacoes(cotas, min_c, max_c, max_e, max_p, max_k)
        else:
            st.error("Nenhuma cota lida. Verifique os dados.")
    else:
        st.error("Cole os dados primeiro.")

# EXIBIÇÃO DO RESULTADO (Persistente)
if st.session_state.df_resultado is not None:
    df_show = st.session_state.df_resultado
    
    if not df_show.empty:
        df_show = df_show.sort_values(by='Custo Real (%)')
        st.success(f"{len(df_show)} Oportunidades Encontradas!")
        
        # Tabela na tela
        st.dataframe(
            df_show,
            column_config={
                "Crédito Total": st.column_config.NumberColumn(format="R$ %.2f"),
                "Entrada Total": st.column_config.NumberColumn(format="R$ %.2f"),
                "Parcela Total": st.column_config.NumberColumn(format="R$ %.2f"),
                "Custo Real (%)": st.column_config.NumberColumn(format="%.2f %%"),
            }, hide_index=True
        )
        
        col_down1, col_down2 = st.columns(2)
        
        # 1. DOWNLOAD PDF
        try:
            pdf_bytes = gerar_pdf_final(df_show)
            col_down1.download_button("📄 Baixar PDF (Paisagem)", pdf_bytes, "JBS_Relatorio.pdf", "application/pdf")
        except Exception as e:
            col_down1.error(f"Erro PDF: {e}")

        # 2. DOWNLOAD EXCEL (FORMATADO)
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
            df_show.to_excel(writer, index=False, sheet_name='JBS')
            wb = writer.book
            ws = writer.sheets['JBS']
            
            # Formatos
            fmt_money = wb.add_format({'num_format': 'R$ #,##0.00'})
            fmt_perc = wb.add_format({'num_format': '0.00%'})
            
            # Aplica formatos
            ws.set_column('C:E', 18, fmt_money) # Crédito, Entrada, Parcela
            ws.set_column('F:F', 12, fmt_perc)  # Custo %
            ws.set_column('G:G', 50)            # Detalhes
            
        col_down2.download_button("📊 Baixar Excel (Formatado)", buf.getvalue(), "JBS_Calculo.xlsx")
        
    else:
        st.warning("Nenhuma oportunidade encontrada com estes filtros.")
