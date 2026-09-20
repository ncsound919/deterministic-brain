---
skill: hunt-distressed-properties
version: 1.0
backend: local
backend_skill_id: ""
description: Run an autonomous distressed-property hunt through the House Flip Studio MCP endpoint, then pull scored/tiered leads and per-property dossiers back into the brain
inputs:
  action: string
  org_id: string
  statewide: boolean
  counties: list
  max_total: number
  require_distress: boolean
  max_purchase_price: number
  tier: string
  limit: number
  address: string
  pin: string
tools: [house_flip_hunt_leads, house_flip_list_leads, house_flip_build_dossier]
audit: []
monte_carlo: false
---
## Step 1
Run the real_estate_leads lane with action=hunt. It calls the House Flip MCP tool
hunt_leads (JSON-RPC tools/call at HOUSE_FLIP_API_URL/api/mcp) with the org's flip
profile, sweeping the county parcel feed for distressed leads.

## Step 2
Read back the result: scanned / newLeads / duplicates / filtered, the tier counts
(hot, warm, cold), and any feed warnings. Every accepted lead carries a documented
motivation signal (absentee, out-of-state, long-held, older home, multi-parcel,
tax delinquent).

## Step 3
Optionally run action=list to rank stored leads by tier, or action=dossier with an
address to compile county tax, deeds, liens, permits, foreclosure, and RentCast data.

## Step 4
Emit the house-flip report as the lane artifact. A hunt that scanned but found
nothing new is reported honestly at lower confidence, never padded with fabricated
leads.
