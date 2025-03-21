import os
import re
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
import fitz  # PyMuPDF

def extract_text_with_positions(input_pdf_path):
    """
    Extrai texto e posições do PDF usando PyMuPDF (fitz).
    Retorna uma lista de dicionários contendo informações sobre cada bloco de texto.
    """
    try:
        doc = fitz.open(input_pdf_path)
        text_data = []
        
        for page_num, page in enumerate(doc):
            blocks = page.get_text("dict")["blocks"]
            page_height = page.rect.height
            
            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"]
                            bbox = span["bbox"]  # (x0, y0, x1, y1)
                            
                            # Converta as coordenadas para o sistema usado pelo reportlab (origem no canto inferior esquerdo)
                            y0 = page_height - bbox[1]
                            y1 = page_height - bbox[3]
                            
                            text_data.append({
                                "page": page_num,
                                "text": text,
                                "x0": bbox[0],
                                "y0": min(y0, y1),  # coordenada y inferior
                                "x1": bbox[2],
                                "y1": max(y0, y1),  # coordenada y superior
                                "original_bbox": bbox
                            })
        
        return text_data
    except Exception as e:
        print(f"Erro ao extrair texto do PDF: {str(e)}")
        return []

def find_student_info_positions(text_data):
    """
    Localiza as posições das linhas que contêm informações do aluno e da matrícula.
    Retorna um dicionário com as coordenadas Y das linhas a serem ocultadas.
    """
    name_positions = []
    registration_positions = []
    
    # Padrões para encontrar linhas com informações de aluno e matrícula
    name_patterns = [r"Aluno\(a\):", r"Nome:"]
    registration_patterns = [r"Matr[íi]cula", r"Registro", r"R\.?A\.?:"]
    
    # Procurar por padrões nas linhas de texto
    for item in text_data:
        text = item["text"].strip()
        
        # Verifica se o texto corresponde a algum padrão de nome
        for pattern in name_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                name_positions.append({
                    "page": item["page"],
                    "y0": item["y0"],
                    "y1": item["y1"],
                    "text": text,
                    "original_bbox": item["original_bbox"]
                })
                break
        
        # Verifica se o texto corresponde a algum padrão de matrícula
        for pattern in registration_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                registration_positions.append({
                    "page": item["page"],
                    "y0": item["y0"],
                    "y1": item["y1"],
                    "text": text,
                    "original_bbox": item["original_bbox"]
                })
                break
    
    # Encontrar todas as linhas que estão na mesma altura da linha com "Aluno(a):"
    # para cobrir a linha inteira, incluindo o nome do aluno
    name_lines_by_page = {}
    for item in text_data:
        for name_pos in name_positions:
            if (item["page"] == name_pos["page"] and 
                abs(item["y0"] - name_pos["y0"]) < 5):  # Tolerância de 5 pontos
                
                if name_pos["page"] not in name_lines_by_page:
                    name_lines_by_page[name_pos["page"]] = {
                        "y_min": float('inf'),
                        "y_max": float('-inf'),
                        "rects": []
                    }
                
                name_lines_by_page[name_pos["page"]]["y_min"] = min(
                    name_lines_by_page[name_pos["page"]]["y_min"], 
                    item["y0"]
                )
                name_lines_by_page[name_pos["page"]]["y_max"] = max(
                    name_lines_by_page[name_pos["page"]]["y_max"], 
                    item["y1"]
                )
                # Armazena também o retângulo original para redação
                name_lines_by_page[name_pos["page"]]["rects"].append(item["original_bbox"])
    
    # Mesmo procedimento para as linhas de matrícula
    registration_lines_by_page = {}
    for item in text_data:
        for reg_pos in registration_positions:
            if (item["page"] == reg_pos["page"] and 
                abs(item["y0"] - reg_pos["y0"]) < 5):  # Tolerância de 5 pontos
                
                if reg_pos["page"] not in registration_lines_by_page:
                    registration_lines_by_page[reg_pos["page"]] = {
                        "y_min": float('inf'),
                        "y_max": float('-inf'),
                        "rects": []
                    }
                
                registration_lines_by_page[reg_pos["page"]]["y_min"] = min(
                    registration_lines_by_page[reg_pos["page"]]["y_min"], 
                    item["y0"]
                )
                registration_lines_by_page[reg_pos["page"]]["y_max"] = max(
                    registration_lines_by_page[reg_pos["page"]]["y_max"], 
                    item["y1"]
                )
                # Armazena também o retângulo original para redação
                registration_lines_by_page[reg_pos["page"]]["rects"].append(item["original_bbox"])
    
    return {
        "name_lines": name_lines_by_page,
        "registration_lines": registration_lines_by_page
    }

def redact_student_info_secure(input_pdf_path, output_pdf_path):
    """
    Redige de forma segura (removendo o texto subjacente) as informações de nome e matrícula em um PDF,
    detectando as linhas relevantes.
    """
    try:
        # Extrair texto e posições
        text_data = extract_text_with_positions(input_pdf_path)
        
        # Se não conseguimos extrair texto, retorne falso
        if not text_data:
            print(f"Não foi possível extrair texto de {input_pdf_path}")
            return False
        
        # Encontrar posições das informações de aluno
        positions = find_student_info_positions(text_data)
        
        # Abrir o PDF com PyMuPDF para redação
        doc = fitz.open(input_pdf_path)
        
        # Para cada página no PDF
        for i, page in enumerate(doc):
            # Retângulo para o nome - se encontrado na página atual
            if i in positions["name_lines"]:
                # Obtenha as dimensões da página
                page_width = page.rect.width
                page_height = page.rect.height
                
                # Crie um retângulo que cubra toda a linha
                y_min = positions["name_lines"][i]["y_min"]
                y_max = positions["name_lines"][i]["y_max"]
                
                # Converta de coordenadas reportlab para PyMuPDF
                y_min_pymupdf = page_height - y_max
                y_max_pymupdf = page_height - y_min
                
                # Adicione margem para garantir que toda a linha seja coberta
                y_min_pymupdf = max(0, y_min_pymupdf - 2)
                y_max_pymupdf = min(page_height, y_max_pymupdf + 2)
                
                # Definir retângulo para toda a largura da página
                rect = fitz.Rect(0, y_min_pymupdf, page_width, y_max_pymupdf)
                
                print(f"Página {i+1}: Redação da linha do nome ({rect})")
                
                # Aplica redação - remove o texto e substitui por um retângulo branco
                # Isso torna o texto não selecionável
                page.add_redact_annot(rect, fill=(1, 1, 1))  # Branco
                page.apply_redactions()
            
            # Retângulo para a matrícula - se encontrada na página atual
            if i in positions["registration_lines"]:
                # Obtenha as dimensões da página
                page_width = page.rect.width
                page_height = page.rect.height
                
                # Crie um retângulo que cubra toda a linha
                y_min = positions["registration_lines"][i]["y_min"]
                y_max = positions["registration_lines"][i]["y_max"]
                
                # Converta de coordenadas reportlab para PyMuPDF
                y_min_pymupdf = page_height - y_max
                y_max_pymupdf = page_height - y_min
                
                # Adicione margem para garantir que toda a linha seja coberta
                y_min_pymupdf = max(0, y_min_pymupdf - 2)
                y_max_pymupdf = min(page_height, y_max_pymupdf + 2)
                
                # Definir retângulo para toda a largura da página
                rect = fitz.Rect(0, y_min_pymupdf, page_width, y_max_pymupdf)
                
                print(f"Página {i+1}: Redação da linha da matrícula ({rect})")
                
                # Aplica redação - remove o texto e substitui por um retângulo branco
                # Isso torna o texto não selecionável
                page.add_redact_annot(rect, fill=(1, 1, 1))  # Branco
                page.apply_redactions()
        
        # Salvar o PDF processado
        doc.save(output_pdf_path)
        doc.close()
        
        return True
    except Exception as e:
        print(f"Erro ao processar {input_pdf_path}: {str(e)}")
        return False

def process_all_pdfs_in_folder(input_folder, output_folder):
    """
    Processa todos os PDFs em uma pasta, removendo informações de nome e matrícula de forma segura.
    """
    # Cria a pasta de saída se não existir
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Conta arquivos processados
    total_files = 0
    successful_files = 0
    
    # Lista todos os arquivos PDF na pasta de entrada
    for filename in os.listdir(input_folder):
        if filename.lower().endswith('.pdf'):
            total_files += 1
            input_path = os.path.join(input_folder, filename)
            output_path = os.path.join(output_folder, f"anon_{filename}")
            
            print(f"\nProcessando: {filename}")
            if redact_student_info_secure(input_path, output_path):
                successful_files += 1
                print(f"✓ Arquivo salvo como: anon_{filename}")
            else:
                print(f"✗ Falha ao processar: {filename}")
    
    print(f"\nProcessamento concluído: {successful_files} de {total_files} arquivos processados com sucesso.")

if __name__ == "__main__":
    # Configurações com pastas padrão
    input_folder = "NotasPDF"
    output_folder = "NotasPDFProcessadas"
    
    # Oferece a opção de alterar as pastas padrão
    use_default = input(f"Usar pastas padrão? (NotasPDF -> NotasPDFProcessadas) [S/n]: ").strip().lower()
    if use_default != 's' and use_default != '':
        input_folder = input("Digite o caminho para a pasta com os PDFs originais: ").strip()
        output_folder = input("Digite o caminho para a pasta onde salvar os PDFs editados: ").strip()
    
    # Garante que as pastas existam
    current_dir = os.path.dirname(os.path.abspath(__file__))
    input_folder = os.path.join(current_dir, input_folder)
    output_folder = os.path.join(current_dir, output_folder)
    
    if not os.path.exists(input_folder):
        os.makedirs(input_folder)
        print(f"\nA pasta de entrada '{input_folder}' foi criada. Por favor, coloque os PDFs nela e execute o script novamente.")
    else:
        # Processa todos os PDFs
        process_all_pdfs_in_folder(input_folder, output_folder)