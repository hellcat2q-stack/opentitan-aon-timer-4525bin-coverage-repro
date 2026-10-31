`timescale 1ns/1ps
`include "uvm_macros.svh"

// Stage 01 tool capability probe only. This is NOT the AON Timer DUT,
// its official coverage model, or input to any reproduction experiment.
package stage01_probe_pkg;
  import uvm_pkg::*;

  class stage01_capability_test extends uvm_test;
    `uvm_component_utils(stage01_capability_test)
    int unsigned sampled_value;

    covergroup capability_cg;
      option.per_instance = 1;
      cp_value: coverpoint sampled_value {
        bins value_zero  = {0};
        bins value_one   = {1};
        bins value_two   = {2};
        bins value_three = {3};
      }
    endgroup

    function new(string name = "stage01_capability_test", uvm_component parent = null);
      super.new(name, parent);
      capability_cg = new();
    endfunction

    task run_phase(uvm_phase phase);
      int sample_count;
      real expected_coverage;
      real observed_coverage;
      phase.raise_objection(this);
      sample_count = $test$plusargs("PROBE_PARTIAL") ? 3 : 4;
      expected_coverage = sample_count * 25.0;
      for (int i = 0; i < sample_count; i++) begin
        sampled_value = i;
        capability_cg.sample();
        #1ns;
      end
      observed_coverage = capability_cg.get_inst_coverage();
      if (observed_coverage != expected_coverage)
        `uvm_fatal("STAGE01_COVERAGE", $sformatf("Expected %0.2f, got %0.2f", expected_coverage, observed_coverage))
      `uvm_info("STAGE01_PROBE", $sformatf("CAPABILITY_PROBE_OK samples=%0d coverage=%0.2f", sample_count, observed_coverage), UVM_NONE)
      phase.drop_objection(this);
    endtask
  endclass
endpackage

module capability_probe;
  import uvm_pkg::*;
  import stage01_probe_pkg::*;
  initial run_test("stage01_capability_test");
endmodule
