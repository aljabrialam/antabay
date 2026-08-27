# Antabay — Architecture & Sequence Diagrams

**Revised 19 August 2026** after the kickoff workshop.

All diagrams reflect the **verified** Atlas contract. Endpoint names, event
names, error codes, and clocks are observed, not assumed. See
`.antabay/atlas-capability-map.md`.

**What changed at kickoff:** Alibaba Cloud is not providing hosting or LLM
API access — participants use their own resources. There is no restriction
on agent framework or spec-driven tooling. AgentScope has therefore been
dropped in favour of a plain FastAPI service with our own ReAct loop: the
only reason to carry framework risk was the "why Alibaba" argument, and
that argument no longer applies. Qwen on Model Studio's free tier is kept
by choice, not obligation.

---

## 1. System architecture

```mermaid
graph TB
    T["Traveller"]

    subgraph UI["Journey Console — React + Vite"]
        OBJ["Objective panel"]
        ST["Journey state + clocks"]
        TR["Agent trace — live event stream"]
        AP["Authorisation gate"]
    end

    subgraph BE["Backend — deployed, long-lived process"]
        subgraph FC["FastAPI service"]
            AG["Antabay Agent<br/>own ReAct loop<br/>Understand → Observe → Reason<br/>→ Act → Verify → Adapt"]
            POL["Authorisation Policy Engine<br/>deterministic — spec 010"]
            RX["Webhook receiver<br/>+ reconciler — spec 007"]
            INJ["Disruption injector<br/>SIMULATED — spec 008"]
        end
        QW["Qwen — Model Studio / DashScope<br/>Singapore, free tier<br/>reasoning only"]
        DB[("Journey state store<br/>objective, orders, clocks,<br/>audit trail, authorisations")]
        LOG["Structured trace + audit log"]
    end

    subgraph TOOL["Atlas Tool Layer — spec 000 contract"]
        SR["search.do"]
        VF["verify.do"]
        OR["order.do"]
        PY["pay.do"]
        QO["queryOrderDetails.do"]
        VD["void / refund"]
    end

    ATLAS[["Atlas Sandbox<br/>sandbox.atriptech.com"]]

    T -->|"goal in natural language"| UI
    UI -->|"SSE event stream"| TR
    AG -->|"emit events"| UI
    AP -->|"approve / decline"| POL

    AG <-->|"reason — never decide authority"| QW
    AG -->|"propose action"| POL
    POL -->|"permitted / requires authorisation"| AG
    AG <-->|"rehydrate + persist"| DB
    AG -->|"every call, decision, approval"| LOG

    AG --> TOOL
    TOOL --> ATLAS
    ATLAS -.->|"order.ticketed — UNAUTHENTICATED"| RX
    INJ -.->|"simulated schedule change"| RX
    RX -->|"untrusted hint"| QO
    QO -->|"authoritative truth"| AG
    RX -->|"wake up"| AG

    classDef sim fill:#4a3a1a,stroke:#c9a227,color:#f5e6c8
    classDef auth fill:#3a1a1a,stroke:#c94f4f,color:#f5d0d0
    class INJ sim
    class POL,AP auth
```

**Four rules the diagram enforces**

1. Qwen reasons. The policy engine decides authority. The line never crosses.
2. Journey state lives outside the agent. Every wake-up rehydrates.
3. Webhooks are untrusted hints. `queryOrderDetails.do` is the truth.
4. Every travel fact shown to the traveller traces to an Atlas response.

---

## 2. Happy path — goal to ticketed

```mermaid
sequenceDiagram
    autonumber
    actor T as Traveller
    participant UI as Console
    participant AG as Antabay Agent
    participant QW as Qwen
    participant POL as Policy Engine
    participant AT as Atlas
    participant DB as State Store

    T->>UI: "Tokyo before 10 AM, under USD 120,<br/>no overnight connections"
    UI->>AG: goal
    AG->>QW: parse into structured objective
    QW-->>AG: destination, deadline, budget,<br/>hard vs soft constraints
    AG->>UI: show parsed objective
    T->>UI: confirm
    AG->>DB: create journey, persist objective

    AG->>AT: search.do
    AT-->>AG: 30 routings + expireTime
    Note over AG: offer clock starts —<br/>observed 7m43s, may arrive pre-aged

    AG->>QW: score against objective
    QW-->>AG: rationale
    Note over AG: reject TW237 — over budget<br/>reject 7C907 via PUS — 10.4h overnight<br/>despite arriving 09:30
    AG->>UI: selected ZE605, USD 90.39, arr 09:50

    AG->>AT: verify.do (routingIdentifier byte-for-byte)
    AT-->>AG: sessionId, priceChange.isPriceChange=false,<br/>bookingRequirement
    Note over AG: offer clock replaced by<br/>session clock (~2h)

    AG->>POL: propose booking — spends money
    POL-->>AG: REQUIRES AUTHORISATION
    AG->>UI: authorisation request
    T->>UI: approve
    AG->>DB: record authorisation

    AG->>AT: order.do (sessionId, passengers, contact)
    AT-->>AG: orderNo, pnrCode, tktLimitTime
    Note over AG: PNR is NOT a ticket.<br/>tktLimitTime clock starts — 30 min

    AG->>AT: pay.do (orderNo)
    AT-->>AG: status 0
    Note over AG: payment success is NOT proof

    loop until ticketNos non-empty
        AG->>AT: queryOrderDetails.do
        AT-->>AG: orderStatus "1", ticketStatus "0", ticketNos []
    end

    AT-)AG: webhook order.ticketed (~35s)
    Note over AG: unauthenticated — treat as hint only
    AG->>AT: queryOrderDetails.do (confirm)
    AT-->>AG: ticketNos ["S46659"]
    AG->>DB: journey MONITORING
    AG->>UI: ticketed, confirmed by order query
```

---

## 3. Disruption and recovery

```mermaid
sequenceDiagram
    autonumber
    actor T as Traveller
    participant UI as Console
    participant INJ as Injector (SIM)
    participant RX as Webhook Receiver
    participant AG as Antabay Agent
    participant POL as Policy Engine
    participant AT as Atlas
    participant DB as State Store

    Note over INJ: sandbox cannot trigger a schedule change.<br/>Envelope mirrors captured order.ticketed shape.<br/>LABELLED SIMULATED — P-13
    T->>UI: trigger disruption
    UI->>INJ: fire
    INJ-)RX: {cid, type: schedule change, status, data}

    RX->>AT: queryOrderDetails.do
    Note over RX: webhook is a hint.<br/>API is the truth — P-05
    AT-->>RX: current order state
    RX-)AG: wake up
    AG->>DB: rehydrate journey + objective

    AG->>AG: evaluate impact
    Note over AG: new arrival 11:50 > deadline 10:00<br/>OBJECTIVE VIOLATED

    AG->>AT: search.do (real data — P-14)
    AT-->>AG: current options
    AG->>AT: verify.do (LJ201)
    AT-->>AG: sessionId, confirmed price

    Note over AG: LJ201 arr 09:55, +USD 6.24 — compliant<br/>TW237 arr 09:30, +USD 51.55 — breaks budget
    AG->>UI: recommend LJ201, +USD 6.24

    AG->>POL: propose rebook + void original
    Note over POL: spends money AND voids a booking<br/>AND is irreversible
    POL-->>AG: REQUIRES AUTHORISATION
    AG->>UI: show cost delta + objective impact

    alt Traveller approves
        T->>UI: approve
        AG->>DB: record authorisation
        AG->>AT: order.do → pay.do (new)
        AT-->>AG: new orderNo
        AG->>AT: void / refund original
        AG->>AT: queryOrderDetails.do (both legs)
        AT-->>AG: confirmed
        AG->>DB: journey updated, MONITORING resumes
    else Traveller declines or does not respond
        T->>UI: decline
        Note over POL: silence is refusal — FR-010
        AG->>DB: record refusal, NO SPEND
        AG->>UI: objective at risk, no action taken
    end
```

---

## 4. Journey state machine

```mermaid
stateDiagram-v2
    [*] --> DRAFT: goal received
    DRAFT --> OBJECTIVE_CONFIRMED: traveller confirms
    OBJECTIVE_CONFIRMED --> SEARCHING: search.do

    SEARCHING --> OPTIONS_HELD: routings returned
    note right of OPTIONS_HELD
        offer clock
        observed 7m43s to 31m
        may arrive pre-aged
    end note

    OPTIONS_HELD --> SEARCHING: offer expired
    OPTIONS_HELD --> VERIFIED: verify.do

    note right of VERIFIED
        session clock ~2h
        offer expireTime now null
    end note

    VERIFIED --> SEARCHING: price changed — P-08
    VERIFIED --> AWAITING_AUTH: policy requires approval
    AWAITING_AUTH --> VERIFIED: declined — no spend
    AWAITING_AUTH --> ORDERED: approved, order.do

    note right of ORDERED
        PNR issued but NOT ticketed
        tktLimitTime — 30 min
    end note

    ORDERED --> RECONCILING: duplicate 318
    RECONCILING --> ORDERED: existing order adopted
    ORDERED --> PAID: pay.do
    PAID --> TICKETED: ticketNos non-empty
    PAID --> RECONCILING: outcome uncertain

    TICKETED --> MONITORING: webhook registered
    MONITORING --> IMPACT_EVAL: schedule change received
    IMPACT_EVAL --> MONITORING: objective still met
    IMPACT_EVAL --> RECOVERY_SEARCH: objective violated
    RECOVERY_SEARCH --> AWAITING_AUTH: recovery proposed
    MONITORING --> [*]: journey complete
```

---

## 5. The three clocks

```mermaid
graph LR
    A["search.do"] -->|"expireTime<br/>7m43s – 31m<br/>may arrive pre-aged"| B["verify.do"]
    B -->|"sessionId<br/>~2 hours"| C["order.do"]
    C -->|"tktLimitTime<br/>30 minutes"| D["pay.do → ticketed"]

    A -.->|expired| A
    B -.->|expired| A
    C -.->|expired| A

    classDef c fill:#1e3a4a,stroke:#4a9fd5,color:#d0e8f5
    class A,B,C,D c
```

Each expiry sends the journey back to search. All three are tracked in
state and displayed in the console with time remaining.
