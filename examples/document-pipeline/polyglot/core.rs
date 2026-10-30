//! Fictional size gate; no actual cross-language bridge is implemented.
pub fn commit(value: &str) -> Result<usize, &'static str> {
    if value.len() > 4096 {
        return Err("document too large");
    }
    Ok(value.len())
}
