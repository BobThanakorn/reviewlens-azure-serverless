# ADR 009: Event Grid delivery role at storage account scope

Status: Accepted

## Context
The design granted the system topic's managed identity `Storage Queue Data Message Sender` on the single `enrich` queue (least privilege). At the first real deploy, creating the event subscription failed three times, over more than ten minutes, with `Managed Identity Authorization Error ... does not have authorization to deliver to the endpoint`. Read-only checks showed the role assignment existed on the queue, was bound to the topic's own principal, the queue existed, and the account allowed the traffic, so it was not an RBAC propagation delay.

Microsoft's Event Grid documentation (delivering events with managed identity) says the identity must hold `Storage Queue Data Message Sender` **on the storage account** that holds the queue.

## Decision
Assign the role at the data storage account scope in `modules/eventing`. The `queue_id` input is removed. The brief's least-privilege intent is kept as far as Event Grid allows: the role only permits sending messages (no read, no delete), and only this system topic's identity holds it.

## Consequences
- The topic identity could in principle send to `enrich-poison` as well; accepted because it can only enqueue messages.
- Changing the scope replaces the role assignment (destroy and create) within Terraform.
- Recorded as a real incident in `docs/runbook.md`.
