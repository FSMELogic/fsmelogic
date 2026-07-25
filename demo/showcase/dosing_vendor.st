// THE UNTRUSTED VENDOR MODULE.
// Imagine this file was AI-generated, or bought from a third party you cannot
// fully audit. secure_plant.st imports it under an EMPTY capability ceiling:
// it may compute, and nothing else. It cannot print, cannot spawn or send,
// cannot touch the clock, the RNG, or the detector -- not because it promises
// not to, but because the language cannot grant it the capability.
module dosing_vendor;

// Chlorine dose (mg/L) for a turbidity reading (NTU). The contract is
// RUNTIME-ENFORCED on every engine: a result outside [0.2, 8.0] halts the
// program at this exact point rather than ever reaching the pump.
fn compute_dose(turbidity: Float) -> Float
    requires turbidity >= 0.0
    ensures result >= 0.2 and result <= 8.0
    intent "map raw turbidity (NTU) to a safe chlorine dose (mg/L)"
    confidence 0.9
    provenance "vendor: aquatech-ai dosing model v3, unaudited"
do
    let raw = 0.2 + turbidity * 0.04;
    clamp(raw, 0.2, 8.0)
end fn

// Validates a raw sensor reading. There is NO null in Stratum: the only way a
// caller can use the value is to destructure Some/None with match, so a bad
// reading can never be dosed by mistake.
fn validate_reading(raw: Float) -> Optional<Float>
    intent "reject physically impossible turbidity readings"
    confidence 0.95
    provenance "vendor: aquatech-ai dosing model v3, unaudited"
do
    match raw do
        when r if r < 0.0 -> None;
        when r if r > 4000.0 -> None;
        when r -> Some(r);
    end match
end fn
