[<-- Back to documentation overview](../documentation.md)

# Cooling-loop setup guidelines

Author: Seb Sikora, March 2021.

Last modified:  Seb Sikora, March 2021.

## Instructions for setting-up the cold-stage recirculating cooling-loop.

## 1. Introduction:

Operation of the solid-state cold-stage requires a continuous supply of coolant media held at ~ +5 deg C. This coolant media acts as a heat source/sink that supplies heat to- or removes heat rejected by the peltier thermoelectric element that forms the active heat-pump within the cold-stage. 

![Fig.1 - Minimal system configuration](images/1_barebones_single_coldstage.png "Fig.1 - Minimal system configuration")

It is recommended that a laboratory recirculating chiller system is used for this purpose, connected to the cold-stage in a closed-loop as shown in it's simplest form in Fig. 1. 

---

## 2. Cooling-loop requirements:

### i. Cooling media:

Consult the documentation provided by the recirculating chiller manufacturer for recommended coolant media. Typically, either a pre-mix solution (eg [Coolflow DTX](https://hydratech-shop.co.uk/collections/process-cooling-fluids/products/coolflow-dtx) - external link) or a solution of ethylene glycol antifreeze, water and a micro-organism inhibitor (eg []() - external link).

As a guideline, the coolant media must have a freezing point below the coldest part of the chiller mechanism, which can be as low as around - 30 deg C. This can be achieved using standard ethylene glycol anti-freeze ...

### ii. Fluid couplers:

![Fig.2 - Cold-stage fluid couplers](images/cold-stage_couplers.png "Fig.2 - Cold-stage fluid couplers")

Locking panel-mount coupling body (external link): [rs-online](https://uk.rs-online.com/web/p/hose-couplings/7640699/)

Locking in-line coupling insert (external link): [rs-online](https://uk.rs-online.com/web/p/hose-couplings/0138385/)

Each cold stage is fitted with two locking hose coupling bodies at the front of the instrument. These mate with corresponding coupling inserts

### iii. Fluid valves:

![Fig.3 - Fluid valves](images/john_guest_valve.png "Fig.3 - Fluid valves")

Blah...

### iv. Cooling capacity (power):

Multiple cold-stages can be connected to a single recirculating chiller, limited by it's total cooling-capacity. Though the heat rejected by a single cold-stage will depend on it's operating condition and applied thermal loads, as a guideline allow ~XXX W of cooling capacity per 30 mm cold-stage or ~XXX W of cooling capacity per 52 mm cold-stage respectively.

If the recirculating chiller is not able to hold the bulk coolant media at or around 5 deg C during cold-stage operation, it indicates that the chosen recirculating chiller does not provide adequate cooling capacity for the desired cold-stage configuration.

### v. Coolant flow-rate:

A coolant flow-rate of ~

---

## 3. Recommended system configuration:

### i. Single cold-stage:

![Fig.4 - Single cold-stage](images/2_recommended_single_coldstage.png "Fig.4 - Single cold-stage recommended configuration")

An example of the simplest system configuration is shown in Fig.4 above, with the recirculating chiller (1) connected to a single cold-stage (2). The recirculating chiller fluid-out port is connected to the cold-stage fluid-in port (blue), while the recirculating chiller fluid-in port is connected to the cold-stage fluid-out port (red). In-line valves (3) are placed at both ends of each run of tubing. This is useful when disconnecting either the recirculating chiller or cold-stage from the system, as the corresponding valves can be closed removing the need to completely drain the fluid circuit.

### ii. Two or more cold-stages:

![Fig.5 - Two cold-stages](images/3_recommended_twin_coldstages.png "Fig.5 - Recommended configuration for two cold-stages")

A single recirculating chiller (1) can be connected to two or more cold-stages (2) via the use of Y-couplers (4) to split the flow of coolant, as shown in Figs.4 & .5. In this case, at a minimum in-line valves (3) are required at the ports of each cold-stage for reasons that will be explained in the next section. 

To ensure that the total coolant flow is split roughly equally between the two cold-stages it is important to try as far as possible to keep the loop of tubing from the Y-couplers to each cold-stage approximately the same length. If this is impossible, the in-line valve at the fluid-in port of the cold-stage connected to the shortest branch (seeing the higher flow) can be partially closed to reduce it's share of the total flow. 

![Fig.6 - Multiple cold-stages](images/4_recommended_n_coldstages.png "Fig.6 - Recommended configuration for multiple cold-stages")

If an odd-number of cold-stages is connected to a single recirculating chiller in this way, it is likely that the odd-cold-stage will see a higher coolant flow rate than the other two cold-stages that share a fluid-in Y-coupler. As described above, the coolant flow can be split between the three cold-stages more evenly by part-closing the in-line valve connected to the fluid-in port of the odd-cold-stage (*) to reduce it's share of the total flow.

---

## 4. Coolant loop priming guide:

If a single recirculating chiller is connected to multiple cold-stages, it will be necessary to include in-line valves in the cooling circuit, at a minimum one at the fluid-in port of each cold stage. This is due to the requirement to completely purge the air from all branches of the cooling circuit at start-up. If the valves are not included, the flow from the recirculating chiller will follow the 'easiest' branch. Cold-stages connected to the other branches will see zero coolant flow. The procedure to ensure that all branches of the circuit circuit are purged of air is explained below. It assumes that the system has been configured as shown in section 3, above.

![Fig.7 - Priming cold-stage 1](images/5_twin_coldstages_priming_1.png "Fig.7 - Priming cold-stage 1")

(i) First ensure that both in-line valves at the recirculating chiller, and at cold-stage (A) are OPEN. CLOSE both in-line valves at cold-stage (B). Then, run the recirculating chiller until you see that all the air has been purged from the branch connected to cold-stage (A).

![Fig.8 - Priming cold-stage 2](images/5_twin_coldstages_priming_2.png "Fig.8 - Priming cold-stage 2")

(ii) Next, close both in-line valves at cold-stage (A) and open both in-line valves at cold-stage (B), then run the recirculating chiller until you see that all the air has been purged from the branch connected to cold-stage (B). Finally, open both in-line valves at cold-stage (A). The coolant circuit is now properly primed and the system is ready to run.

If more than two cold-stages are connected, the same process applies. Open the in-line valves at only *one* cold-stage in turn, running the recirculating chiller each time until the air in the branch connected to that cold-stage has been displaced by the coolant.

---

## 5. Care tips:

Blah...

---
