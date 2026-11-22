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

const NOME_TESTE: &str = "Periodo de teste";
const DIAS_TESTE: i64 = 30;

// Todo computador novo ganha 30 dias de teste na primeira vez que aparece.
// Um ID que já está no arquivo (inclusive bloqueado) não é alterado.
pub fn garantir_teste(id: &str) {
    use std::collections::HashSet;
    use std::io::Write;
    use std::sync::{Mutex, OnceLock};
    static VISTOS: OnceLock<Mutex<HashSet<String>>> = OnceLock::new();
    if std::env::var("ADL_LICENCAS").map(|v| v == "0").unwrap_or(false) {
        return;
    }
    let vistos = VISTOS.get_or_init(|| Mutex::new(HashSet::new()));
    let mut vistos = match vistos.lock() {
        Ok(v) => v,
        Err(_) => return,
    };
    if vistos.contains(id) {
        return;
    }
    let conteudo = std::fs::read_to_string(ARQUIVO).unwrap_or_default();
    let existe = conteudo
        .lines()
        .any(|l| l.trim().split(';').next().map(|x| x.trim() == id).unwrap_or(false));
    if !existe {
        let vence = (chrono::Utc::now() + chrono::Duration::days(DIAS_TESTE))
            .format("%Y-%m-%d")
            .to_string();
        let prefixo = if conteudo.is_empty() || conteudo.ends_with('\n') { "" } else { "\n" };
        match std::fs::OpenOptions::new().create(true).append(true).open(ARQUIVO) {
            Ok(mut f) => {
                if writeln!(f, "{}{};{};{}", prefixo, id, vence, NOME_TESTE).is_err() {
                    return;
                }
                hbb_common::log::info!("ADL Suporte: {} recebeu teste ate {}", id, vence);
            }
            Err(_) => return,
        }
    }
    vistos.insert(id.to_owned());
}
