import pdfplumber
import pandas as pd
import os

def eh_linha_valida(linha):
    if not linha or len(linha) < 8:
        return False
    
    if not linha[0] or not ('/' in linha[0] or linha[0].startswith(('DC', 'DMAT', 'DFIS'))):
        return False
    
    if not linha[1]:
        return False
    
    return any(i < len(linha) and linha[i] and any(c.isdigit() for c in linha[i]) for i in range(2, 5))

def extrair_notas_pasta(pasta_pdfs, csv_completo):
    df_final = pd.DataFrame()
    arquivos_pdf = [f for f in os.listdir(pasta_pdfs) if f.endswith(".pdf")]
    
    for idx, arquivo in enumerate(sorted(arquivos_pdf), start=1):
        pdf_path = os.path.join(pasta_pdfs, arquivo)
        dados = extrair_dados_do_pdf(pdf_path, idx)
        df = criar_dataframe(dados)
        df_final = pd.concat([df_final, df], ignore_index=True)
    
    salvar_datasets(df_final, csv_completo)
    print(f"Dataset gerado com sucesso: {csv_completo}")

def extrair_dados_do_pdf(pdf_path, aluno_id):
    dados = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tabelas = page.extract_tables()
            if tabelas:
                for tabela in tabelas:
                    for linha in tabela:
                        if eh_linha_valida(linha):
                            dados.append([aluno_id] + linha)
    return dados

def criar_dataframe(dados):
    if not dados:
        return pd.DataFrame()
    
    max_cols = max(len(linha) for linha in dados)
    colunas = ["AlunoID", "Código", "Disciplina", "Unidade 1", "Unidade 2", "Unidade 3", "Unidade 4", "Unidade 5", "Prova Final", "Resultado", "Faltas", "Situação"]
    colunas = colunas[:max_cols] if max_cols <= len(colunas) else colunas + [f"Col{i}" for i in range(len(colunas)+1, max_cols+1)]
    
    return pd.DataFrame(dados, columns=colunas)

def salvar_datasets(df, csv_completo):
    df.to_csv(csv_completo, index=False)

if __name__ == "__main__":
    pasta_pdfs = "./NotasPDF"
    extrair_notas_pasta(pasta_pdfs, "Datasets/notas_alunos.csv")
