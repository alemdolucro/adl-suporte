// ADL Suporte: controle de licenças por ID.
// Arquivo licencas.txt no diretório de trabalho, uma linha por computador:
// ID;AAAA-MM-DD;nome do cliente
// Um ID fica acessível só se estiver no arquivo e com vencimento a partir de hoje.
// ADL_LICENCAS=0 desliga a trava.

const ARQUIVO: &str = "licencas.txt";

pub fn licenca_ativa(id: &str) -> bool {
    if std::env::var("ADL_LICENCAS").map(|v| v == "0").unwrap_or(false) {
        return true;
    }
    let conteudo = match std::fs::read_to_string(ARQUIVO) {
        Ok(c) => c,
        Err(_) => return false,
    };
    let hoje = chrono::Utc::now().format("%Y-%m-%d").to_string();
    conteudo.lines().any(|linha| {
        let mut partes = linha.trim().split(';');
        let lid = partes.next().unwrap_or("").trim();
        let vence = partes.next().unwrap_or("").trim();
        !lid.is_empty() && lid == id && vence.len() == 10 && vence >= hoje.as_str()
    })
}
