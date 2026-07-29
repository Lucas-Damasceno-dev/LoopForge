use std::fs::File;
use std::io::Write;

pub struct DollarQuote {
    pub date: String,
    pub bid: f64,
    pub ask: f64,
}

impl DollarQuote {
    pub fn to_csv_line(&self) -> String {
        format!("{},{:.4},{:.4}\n", self.date, self.bid, self.ask)
    }
}

pub fn save_quote_to_csv(filepath: &str, quote: &DollarQuote) -> std::io::Result<()> {
    let mut file = File::create(filepath)?;
    file.write_all(b"date,bid,ask\n")?;
    file.write_all(quote.to_csv_line().as_bytes())?;
    Ok(())
}

fn main() {
    println!("🦀 LoopForge Rust Dollar Quote CLI");
    let quote = DollarQuote {
        date: "2026-07-29".to_string(),
        bid: 5.4215,
        ask: 5.4250,
    };
    if let Err(e) = save_quote_to_csv("dollar_quote.csv", &quote) {
        eprintln!("Erro ao salvar CSV: {}", e);
    } else {
        println!("✔ Cotação do dólar salva com sucesso em 'dollar_quote.csv'.");
    }
}
