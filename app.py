
import streamlit as st
import pandas as pd
import re
import itertools
from io import BytesIO

st.set_page_config(page_title="Sniper de Consórcio", page_icon="🎯", layout="wide")

# --- FUNÇÕES ---
def limpar_moeda(texto):
    if not texto: return 0.0
    texto = str(texto).lower().strip()
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
    # Tenta quebrar por blocos duplos, senão linha a linha
    blocos = re.split(r'\n\s*\n', texto_copiado)
    if len(blocos) < 5: blocos = texto_copiado.split('\n')

    id_cota = 1
    for bloco in blocos:
        if len(bloco) < 10: continue
        bloco_lower = bloco.lower()
        
        admins_conhecidas = ['BRADESCO', 'SANTANDER', 'ITAÚ', 'ITAU', 'PORTO', 'CAIXA', 'BANCO DO BRASIL', 'BB', 'RODOBENS', 'EMBRACON', 'ANCORA', 'ÂNCORA', 'MYCON', 'SICREDI', 'SICOOB', 'MAPFRE', 'HS', 'YAMAHA', 'ZEMA']
        admin_encontrada = "DESCONHECIDA"
        for adm in admins_conhecidas:
            if adm.lower() in bloco_lower:
                admin_encontrada = adm.upper()
                break
        
        if admin_encontrada == "DESCONHECIDA" and "r$" not in bloco_lower: continue

        credito = 0.0
        match_cred = re.search(r'(?:crédito|credito|bem|valor).*?R\$\s?([\d\.,]+)', bloco_lower)
        if match_cred: credito = limpar_moeda(match_cred.group(1))
        else:
            valores = re.findall(r'R\$\s?([\d\.,]+)', bloco)
            vals_float = [limpar_moeda(v) for v in valores]
            vals_float.sort(reverse=True)
            if vals_float: credito = vals_float[0]

        entrada = 0.0
        match_ent = re.search(r'(?:entrada|ágio|agio|quero|pago).*?R\$\s?([\d\.,]+)', bloco_lower)
        if match_ent: entrada = limpar_moeda(match_ent.group(1))
        else:
            valores = re.findall(r'R\$\s?([\d\.,]+)', bloco)
            vals_float = [limpar_moeda(v) for v in valores]
            vals_float.sort(reverse=True)
            if len(vals_float) > 1: entrada = vals_float[1]

        regex_parcelas = r'(\d+)\s*[xX]\s*R?\$\s?([\d\.,]+)'
        todas_parcelas = re.findall(regex_parcelas, bloco)
        
        saldo_devedor = 0.0
        parcela_teto = 0.0
        for prazo_str, valor_str in todas_parcelas:
            pz = int(prazo_str)
            vlr = limpar_moeda(valor_str)
            saldo_devedor += (pz * vlr)
            if pz > 1 and vlr > parcela_teto: parcela_teto = vlr
            elif len(todas_parcelas) == 1: parcela_teto = vlr

        if credito > 0 and entrada > 0 and saldo_devedor > 0:
            custo_total = entrada + saldo_devedor
            custo_real_pct = (custo_total / credito) - 1
            if custo_real_pct < 0.80: 
                lista_cotas.append({
                    'ID': id_cota,
                    'Admin': admin_encontrada,
                    'Crédito': credito,
                    'Entrada': entrada,
                    'Parcela': parcela_teto,
                    'Saldo': saldo_devedor,
                    'CustoTotal': custo_total,
                    'EntradaPct': (entrada/credito)
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
    status_text = st.empty()
    total_admins = len(cotas_por_admin)
    current_admin = 0

    for admin, grupo in cotas_por_admin.items():
        if admin == "DESCONHECIDA": continue
        current_admin += 1
        progress = int((current_admin / total_admins) * 100)
        progress_bar.progress(progress)
        status_text.text(f"Analisando {admin}...")
        
        if sum(c['Crédito'] for c in grupo) < min_cred: continue
        
        # SMART SORT V18
        grupo.sort(key=lambda x: x['EntradaPct'])
        
        count = 0
        max_ops = 3000000 
        
        for r in range(1, 7):
            iterator = itertools.combinations(grupo, r)
            while True:
                try:
                    combo = next(iterator)
                    count += 1
                    if count > max_ops: break
                    
                    soma_ent = sum(c['Entrada'] for c in combo)
                    if soma_ent > (max_ent * 1.02): continue
                    
                    soma_cred = sum(c['Crédito'] for c in combo)
                    if soma_cred < min_cred or soma_cred > max_cred: continue
                    
                    soma_parc = sum(c['Parcela'] for c in combo)
                    if soma_parc > (max_parc * 1.05): continue
                    
                    soma_custo = sum(c['CustoTotal'] for c in combo)
                    custo_real = (soma_custo / soma_cred) - 1
                    if custo_real > max_custo: continue
                    
                    # Match
                    ids = " + ".join([str(c['ID']) for c in combo])
                    detalhes = " || ".join([f"[ID {c['ID']}] Cr: {c['Crédito']:,.0f} Ent: {c['Entrada']:,.0f}" for c in combo])
                    
                    status = "⚠️ CUSTO ELEVADO"
                    if custo_real <= 0.20: status = "💎 LUCRO/DESÁGIO"
                    elif custo_real <= 0.40: status = "🔥 IMPERDÍVEL"
                    elif custo_real <= 0.50: status = "✅ BOA"
                    elif custo_real <= 0.55: status = "✅ MERCADO"
                    
                    combinacoes_validas.append({
                        'Admin': admin,
                        'Status': status,
                        'IDs': ids,
                        'Crédito Total': soma_credito,
                        'Entrada Total': soma_entrada,
                        'Parcela Total': soma_parcela,
                        'Custo Real (%)': custo_real,
                        'Detalhes': detalhes
                    })
                    
                    if len([x for x in combinacoes_validas if x['Admin'] == admin]) > 300: break
                except StopIteration:
                    break
            if count > max_ops: break
            
    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(combinacoes_validas)

# --- INTERFACE ---
st.title("🎯 Sniper de Consórcio")
st.markdown("**Versão Mobile V22 (Engenharia Reversa)**")

with st.expander("📋 Passo 1: Colar Dados do Site", expanded=True):
    texto_site = st.text_area("Cole aqui (CTRL+A / CTRL+C do site)", height=150, placeholder="Role o site até o final, copie tudo e cole aqui...")

st.subheader("⚙️ Passo 2: Perfil do Cliente")
col1, col2 = st.columns(2)

with col1:
    min_c = st.number_input("Crédito Mínimo", value=640000, step=10000)
    max_c = st.number_input("Crédito Máximo", value=710000, step=10000)

with col2:
    max_e = st.number_input("Entrada Máxima (R$)", value=280000, step=5000)
    max_p = st.number_input("Parcela Teto (R$)", value=4500, step=100)

max_k = st.slider("Custo Real Máximo (%)", 0.0, 1.0, 0.55, 0.01)

if st.button("🚀 Processar Oportunidades", type="primary"):
    if not texto_site:
        st.error("Por favor, cole os dados do site primeiro!")
    else:
        with st.spinner('O Robô está pensando... (Isso pode levar alguns segundos)'):
            cotas = extrair_dados_universal(texto_site)
            
            if len(cotas) > 0:
                df_result = processar_combinacoes(cotas, min_c, max_c, max_e, max_p, max_k)
                
                if not df_result.empty:
                    df_result = df_result.sort_values(by='Custo Real (%)')
                    st.success(f"Encontrei {len(df_result)} combinações!")
                    
                    # Formatação Visual na Tabela
                    st.dataframe(
                        df_result,
                        column_config={
                            "Crédito Total": st.column_config.NumberColumn(format="R$ %.2f"),
                            "Entrada Total": st.column_config.NumberColumn(format="R$ %.2f"),
                            "Parcela Total": st.column_config.NumberColumn(format="R$ %.2f"),
                            "Custo Real (%)": st.column_config.NumberColumn(format="%.2f %%"),
                        },
                        hide_index=True
                    )
                    
                    # Excel
                    buffer = BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        df_result.to_excel(writer, index=False, sheet_name='Sniper')
                        wb = writer.book
                        ws = writer.sheets['Sniper']
                        fmt_money = wb.add_format({'num_format': 'R$ #,##0.00'})
                        fmt_perc = wb.add_format({'num_format': '0.00%'})
                        ws.set_column('D:F', 18, fmt_money)
                        ws.set_column('G:G', 12, fmt_perc)
                        
                    st.download_button(
                        label="📥 Baixar Excel Completo",
                        data=buffer.getvalue(),
                        file_name="oportunidades_sniper.xlsx",
                        mime="application/vnd.ms-excel"
                    )
                else:
                    st.warning("Nenhuma combinação encontrada. Tente relaxar os filtros.")
            else:
                st.error("Não consegui ler nenhuma cota. Verifique a cópia.")
