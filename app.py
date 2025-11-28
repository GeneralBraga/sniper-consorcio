
import streamlit as st
import pandas as pd
import re
import itertools
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from io import BytesIO
from fpdf import FPDF
from datetime import datetime
import os

# --- CORES DA MARCA ---
COLOR_GOLD = "#84754e"
COLOR_BEIGE = "#ecece4"
COLOR_BG = "#0e1117"

st.set_page_config(page_title="JBS Sniper | Sistema Premium", page_icon="🏛️", layout="wide")

# CSS PERSONALIZADO
st.markdown(f"""
<style>
    .stApp {{background-color: {COLOR_BG}; color: {COLOR_BEIGE};}}
    .stButton>button {{width: 100%; background-color: {COLOR_GOLD}; color: white; border-radius: 6px; font-weight: bold;}}
    .stButton>button:hover {{background-color: #6b5e3d; color: {COLOR_BEIGE}; border: 1px solid {COLOR_BEIGE};}}
    h1, h2, h3 {{color: {COLOR_GOLD} !important; font-family: 'Helvetica', sans-serif;}}
    .stTextInput>div>div>input, .stNumberInput>div>div>input {{background-color: #1c1f26; color: white; border: 1px solid {COLOR_GOLD};}}
</style>
""", unsafe_allow_html=True)

# --- CABEÇALHO ---
c1, c2 = st.columns([1, 5])
with c1:
    if os.path.exists("logo.png"): st.image("logo.png", width=120)
    else: st.markdown(f"<h2 style='color:{COLOR_GOLD}'>JBS</h2>", unsafe_allow_html=True)
with c2:
    st.markdown(f"# SISTEMA SNIPER V27")
    st.markdown(f"**JBS Contempladas** | Inteligência Comercial")
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
                        'Custo Real (%)': custo_real * 100, # MULTIPLICADO POR 100
                        'Detalhes': detalhes
                    })
                    
                    if len([x for x in combinacoes_validas if x['Admin'] == admin]) > 150: break
                except StopIteration: break
            if count > max_ops: break
    progress_bar.empty()
    return pd.DataFrame(combinacoes_validas)

# --- FUNÇÃO GOOGLE SHEETS (REAL) ---
def criar_planilha_google(df):
    try:
        # Tenta pegar as credenciais dos "Secrets" do Streamlit
        # O usuário precisa configurar isso no painel do Streamlit Cloud
        if "gcp_service_account" not in st.secrets:
            return None, "⚠️ Configure as chaves de API do Google no Streamlit Cloud."

        # Conecta
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Cria Planilha
        nome_arquivo = f"JBS_Oportunidades_{datetime.now().strftime('%d-%m-%H-%M')}"
        sh = client.create(nome_arquivo)
        
        # Compartilha com quem criou (opcional, mas bom pra garantir acesso)
        # sh.share('seu_email@jbs.com.br', perm_type='user', role='writer') 
        
        worksheet = sh.get_worksheet(0)
        
        # Upload dos dados (converte tudo para string para evitar erros de JSON)
        df_str = df.astype(str)
        worksheet.update([df_str.columns.values.tolist()] + df_str.values.tolist())
        
        return sh.url, "Sucesso"
    except Exception as e:
        return None, f"Erro na API: {str(e)}"

# --- PDF FIX ---
class PDF(FPDF):
    def header(self):
        self.set_fill_color(132, 117, 78)
        self.rect(0, 0, 297, 20, 'F')
        self.set_font('Arial', 'B', 14)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, 'JBS CONTEMPLADAS', 0, 1, 'C')
        self.ln(5)

def gerar_pdf_simples(df):
    pdf = PDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Arial", size=9)
    pdf.set_fill_color(220, 220, 220)
    pdf.set_text_color(0)
    headers = ["Admin", "Status", "Credito", "Entrada", "Parcela", "Custo %", "Detalhes"]
    w = [35, 35, 35, 35, 35, 20, 80]
    for i, h in enumerate(headers): pdf.cell(w[i], 8, h, 1, 0, 'C', True)
    pdf.ln()
    for index, row in df.iterrows():
        detalhe = str(row['Detalhes']).encode('latin-1', 'ignore').decode('latin-1')
        status = str(row['Status']).encode('latin-1', 'ignore').decode('latin-1')
        pdf.cell(w[0], 8, str(row['Admin']), 1, 0, 'C')
        pdf.cell(w[1], 8, status, 1, 0, 'C')
        pdf.cell(w[2], 8, f"R$ {row['Crédito Total']:,.2f}", 1, 0, 'R')
        pdf.cell(w[3], 8, f"R$ {row['Entrada Total']:,.2f}", 1, 0, 'R')
        pdf.cell(w[4], 8, f"R$ {row['Parcela Total']:,.2f}", 1, 0, 'R')
        pdf.cell(w[5], 8, f"{row['Custo Real (%)']:.2f}%", 1, 0, 'C')
        pdf.cell(w[6], 8, detalhe[:45], 1, 1, 'L')
    return pdf.output(dest='S').encode('latin-1', 'replace')

# --- UI ---
with st.expander("📋 DADOS DO SITE (Colar aqui)", expanded=True):
    texto_site = st.text_area("", height=100)

st.subheader("Filtros JBS")
c1, c2 = st.columns(2)
# FORMATAÇÃO DO INPUT (Visual apenas, o valor é float)
min_c = c1.number_input("Crédito Mín (R$)", 640000.0, step=10000.0, format="%.2f")
max_c = c1.number_input("Crédito Máx (R$)", 710000.0, step=10000.0, format="%.2f")
max_e = c2.number_input("Entrada Máx (R$)", 280000.0, step=5000.0, format="%.2f")
max_p = c2.number_input("Parcela Máx (R$)", 4500.0, step=100.0, format="%.2f")
max_k = st.slider("Custo Máx (%)", 0.0, 1.0, 0.55, 0.01)

if st.button("🔍 LOCALIZAR OPORTUNIDADES"):
    if texto_site:
        cotas = extrair_dados_universal(texto_site)
        if cotas:
            df = processar_combinacoes(cotas, min_c, max_c, max_e, max_p, max_k)
            if not df.empty:
                df = df.sort_values(by='Custo Real (%)')
                st.success(f"{len(df)} Oportunidades Encontradas!")
                
                st.dataframe(
                    df,
                    column_config={
                        "Crédito Total": st.column_config.NumberColumn(format="R$ %.2f"),
                        "Entrada Total": st.column_config.NumberColumn(format="R$ %.2f"),
                        "Parcela Total": st.column_config.NumberColumn(format="R$ %.2f"),
                        "Custo Real (%)": st.column_config.NumberColumn(format="%.2f %%"),
                    }, hide_index=True
                )
                
                c_pdf, c_xls, c_goog = st.columns(3)
                
                # PDF
                try:
                    pdf_data = gerar_pdf_simples(df)
                    c_pdf.download_button("📄 Baixar PDF", pdf_data, "JBS.pdf", "application/pdf")
                except: c_pdf.error("Erro PDF")

                # Excel
                buf = BytesIO()
                with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False)
                c_xls.download_button("📊 Baixar Excel", buf.getvalue(), "JBS.xlsx")
                
                # Google Sheets (Botão Condicional)
                if c_goog.button("🌐 Gerar Link Google Sheets"):
                    url, msg = criar_planilha_google(df)
                    if url: st.success(f"Link Criado: [Abrir Planilha]({url})")
                    else: st.error(f"Erro: {msg}")
            else:
                st.warning("Nenhuma oportunidade encontrada.")
    else:
        st.error("Cole os dados primeiro.")
