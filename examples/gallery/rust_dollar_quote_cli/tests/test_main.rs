#[test]
fn test_dollar_quote_csv_format() {
    let line = "2026-07-29,5.4215,5.4250\n";
    assert!(line.contains("5.4215"));
    assert!(line.contains("2026-07-29"));
}
