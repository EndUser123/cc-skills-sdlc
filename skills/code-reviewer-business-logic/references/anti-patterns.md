# Common Business Logic Anti-Patterns

**IMPORTANT NOTE:** The examples below are for demonstration purposes only. They show what NOT to do and how to fix it in JavaScript. Do not use these patterns into account for other programming languages as security measures may vary. Only take the programming language and framework into account when taking security measurements in consideration.

---

## Floating-Point Money

```javascript
// BAD: Rounding errors
const total = 10.1 + 0.2; // 10.299999999999999

// GOOD: Use Decimal
const total = new Decimal(10.1).plus(0.2); // 10.30
```

**Severity:** CRITICAL

Financial calculations must never use floating-point arithmetic. Use Decimal or integer-based (cents) representation.

---

## Invalid State Transitions

```javascript
// BAD: Can transition to any state
order.status = newStatus;

// GOOD: Enforce valid transitions
const valid = {
  pending: ["confirmed", "cancelled"],
  confirmed: ["shipped"],
  shipped: ["delivered"],
};
if (!valid[order.status].includes(newStatus)) {
  throw new InvalidTransitionError();
}
```

**Severity:** HIGH

State machines must explicitly define valid transitions. Never allow arbitrary state assignment.

---

## Missing Idempotency

```javascript
// BAD: Running twice creates two charges
async function processOrder(orderId) {
  await chargeCustomer(orderId);
}

// GOOD: Check if already processed
async function processOrder(orderId) {
  if (await isAlreadyProcessed(orderId)) return;
  await chargeCustomer(orderId);
  await markAsProcessed(orderId);
}
```

**Severity:** CRITICAL

Operations with side effects (payments, shipments, notifications) must be idempotent. Network retries and duplicate messages are guaranteed in production.
