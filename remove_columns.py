import pandas as pd

def remover_colunas(csv_entrada, csv_saida):
    # Carrega o dataset
    df = pd.read_csv(csv_entrada)
    
    # Remove as colunas desnecessárias
    colunas_remover = ["Unidade 4", "Unidade 5", "Faltas"]
    df = df.drop(columns=[col for col in colunas_remover if col in df.columns])
    
    # Salva o dataset atualizado
    df.to_csv(csv_saida, index=False)
    print(f"Arquivo salvo como: {csv_saida}")

# Executa a função
csv_entrada = "Datasets/notas_alunos.csv"
csv_saida = "Datasets/notas_alunos_limpo.csv"
remover_colunas(csv_entrada, csv_saida)