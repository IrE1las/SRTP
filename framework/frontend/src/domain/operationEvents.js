// The pending envelope contains no operation PIN. Reuse its event ID after
// an uncertain response so a network retry cannot become a second click.
export function eventEnvelope(action, sequence, values = {}, eventId = crypto.randomUUID()) {
  return { event_id: eventId, sequence, action, ...values }
}
export function persistableEvent(event) {
  const { pin, ...safe } = event
  return safe
}
export function initialForm() {
  return { title: '', prompt: '', classes: [], initial: { interval_available: true, occupied_sections: [] } }
}
export function draftPayload(form, classText) {
  return {
    title: form.title || null, prompt: form.prompt || null,
    classes: [...new Set((Array.isArray(classText) ? classText : classText.split(/[,，\n]/)).map(v => v.trim()).filter(Boolean))],
    initial: { interval_available: form.initial.interval_available, occupied_sections: [...form.initial.occupied_sections] },
  }
}
