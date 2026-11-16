import { computed, reactive, ref } from 'vue'

export function useKnowledgeLibrary(api) {
  const documents = ref([]),
    selected = ref(null),
    loading = ref(false),
    saving = ref(false)
  const query = ref(''),
    filter = ref('all'),
    page = ref(1)
  const form = reactive({ title: '', description: '', enabled: false })
  let selectionVersion = 0
  const filtered = computed(() =>
    documents.value.filter((d) => {
      const matches = `${d.title} ${d.filename} ${d.description}`
        .toLowerCase()
        .includes(query.value.trim().toLowerCase())
      return (
        matches &&
        (filter.value === 'all' ||
          (filter.value === 'enabled'
            ? d.enabled && d.status === 'ready'
            : !d.enabled || d.status !== 'ready'))
      )
    }),
  )
  const currentPage = computed(
    () => selected.value?.pages?.[page.value - 1] || null,
  )
  const dirty = computed(
    () =>
      !!selected.value &&
      ['title', 'description', 'enabled'].some(
        (k) => form[k] !== selected.value[k],
      ),
  )
  function accept(doc) {
    selected.value = doc
    Object.assign(form, {
      title: doc.title,
      description: doc.description,
      enabled: doc.enabled,
    })
    page.value = 1
  }
  async function select(id) {
    const version = ++selectionVersion
    loading.value = true
    try {
      const doc = await api.getMaterial(id)
      if (version === selectionVersion) accept(doc)
    } finally {
      if (version === selectionVersion) loading.value = false
    }
  }
  async function reload(preferred = selected.value?.id) {
    documents.value = await api.listMaterials()
    const id = documents.value.some((d) => d.id === preferred)
      ? preferred
      : documents.value[0]?.id
    if (id) await select(id)
    else {
      selectionVersion++
      selected.value = null
      loading.value = false
    }
  }
  async function save() {
    if (!selected.value || saving.value || loading.value) return
    saving.value = true
    try {
      const doc = await api.editMaterial(selected.value.id, {
        ...form,
        revision: selected.value.revision,
      })
      accept(doc)
      documents.value = documents.value.map((d) => (d.id === doc.id ? doc : d))
    } finally {
      saving.value = false
    }
  }
  async function remove() {
    if (!selected.value || saving.value) return
    saving.value = true
    try {
      const result = await api.deleteMaterial(
        selected.value.id,
        selected.value.revision,
      )
      await reload()
      return result
    } finally {
      saving.value = false
    }
  }
  return {
    documents,
    selected,
    loading,
    saving,
    query,
    filter,
    page,
    form,
    filtered,
    currentPage,
    dirty,
    select,
    reload,
    save,
    remove,
  }
}
