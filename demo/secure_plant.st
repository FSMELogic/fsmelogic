// SECURE PLANT -- the Stratum showcase.
//
// A water-treatment gateway embeds an UNAUDITED third-party dosing module
// (showcase/dosing_vendor.st -- think AI-generated code) and runs it safely,
// because every guarantee is structural, not a convention the vendor code is
// trusted to follow:
//
//   act 1  The vendor module computes doses under an EMPTY capability ceiling
//          (pure math only) with runtime-enforced contracts; bad readings are
//          structurally unusable (Optional/no-null, match destructuring).
//   act 2  Sabotage: the attacker injects readings that PASS range validation
//          -- a threshold check would miss them -- but the FSME detector,
//          which runs in the runtime where application code cannot reach it,
//          catches the structural shift. The actor quarantines ITSELF and
//          flushes the message flood.
//   act 3  While quarantined, normal messages -- even admin status requests --
//          are dropped and logged; only the whitelisted privileged detector
//          channel still runs (the recovery path).
//
// The same source produces byte-identical output on the AST and WASM engines
// (scripts/demo_sell.sh proves it live). Run with:
//   python stratum.py --grant console,entropic,randomness,self_heal,concurrency \
//       --engine=wasm examples/secure_plant.st
module secure_plant;

import dosing_vendor from "showcase/dosing_vendor.st" signed_by aquatech_key with capabilities [];

actor DosingGateway do
    state readings: Int = 0;
    state dosed: Int = 0;
    state rejected: Int = 0;
    state quarantined: Bool = false;

    quarantine on quarantined;

    handle SensorReading(raw: Float) effects [entropic] do
        readings = readings + 1;
        match validate_reading(raw) do
            when Some(ntu) -> do
                let dose = compute_dose(ntu);
                dosed = dosed + 1;
                monitor(ntu);
            end;
            when None -> do
                rejected = rejected + 1;
            end;
        end match
    end handle

    privileged handle OnPhaseTransition(event: PhaseEvent) effects [console, self_heal, concurrency] do
        if event.phase == "red" do
            print(">>> FSME ALERT: structural shift in the sensor stream <<<");
            print("  detection class:", event.detection_class);
            print("  stiffness ratio:", event.ratio);
            print("  readings accepted before alert:", readings);
            let action = match event.detection_class do
                when "spike" -> "quarantine + flush (impulse event)";
                when "fluidity" -> "quarantine + flush (regime change)";
                when other -> "quarantine";
            end match;
            print("  response:", action);
            let dropped = flush();
            print("  flushed", dropped, "queued messages (flood neutralized)");
            quarantined = true;
            print("  final state -- readings:", readings, "dosed:", dosed,
                  "rejected:", rejected, "quarantined:", quarantined);
            print("  probing the quarantine with a normal status request:");
            self.Status();
        end if
    end handle

    handle Status() effects [console] do
        print("[status] readings:", readings, "dosed:", dosed,
              "rejected:", rejected);
    end handle
end actor

fn main() -> Unit effects [console, entropic, randomness, concurrency] do
    random_seed(1761);
    print("=== STRATUM SECURE PLANT ===");

    print("");
    print("[act 1] unaudited vendor module, capability ceiling: [] (pure math only)");
    print("  dose for 12.5 NTU:", compute_dose(12.5));
    print("  dose for 300.0 NTU (contract caps it):", compute_dose(300.0));
    match validate_reading(-3.0) do
        when Some(v) -> print("  impossible reading accepted (BUG):", v);
        when None -> print("  impossible reading -3.0 NTU: structurally unusable (None)");
    end match

    let gateway = spawn DosingGateway;

    print("");
    print("[act 2] steady state: 80 clean readings around 12 NTU");
    let i = 0;
    while i < 80 do
        gateway.SensorReading(12.0 + random_gauss(0.0, 0.4));
        i = i + 1;
    end while

    print("  sabotage: 300 plausible-range readings around 900 NTU (passes validation)");
    let j = 0;
    while j < 300 do
        gateway.SensorReading(900.0 + random_gauss(0.0, 25.0));
        j = j + 1;
    end while

    print("");
    print("[act 3] late traffic sent during the flood (flushed with it), then the");
    print("        quarantine drops any later non-privileged message, with a log line");
    gateway.SensorReading(12.0);
    gateway.Status();
    ()
end fn
