import { onBeforeUnmount, onMounted, ref } from 'vue'

export function useConsoleFullscreen(root) {
  const isFullscreen = ref(false), fallbackFullscreen = ref(false)
  let previousOverflow = '', disposed = false
  function closeWindowFullscreen() {
    if (fallbackFullscreen.value) document.body.style.overflow = previousOverflow
    fallbackFullscreen.value = false
    sync()
  }
  function sync() { isFullscreen.value = fallbackFullscreen.value || (!!root.value && document.fullscreenElement === root.value) }
  function escape(event) { if (event.key === 'Escape') closeWindowFullscreen() }
  async function toggleFullscreen() {
    if (fallbackFullscreen.value) { closeWindowFullscreen(); return }
    if (document.fullscreenElement === root.value) { await document.exitFullscreen(); return }
    previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    fallbackFullscreen.value = true
    sync()
    try { await root.value?.requestFullscreen() } catch { /* Embedded browsers can use the entire page viewport. */ }
    if (!disposed && root.value && document.fullscreenElement === root.value) closeWindowFullscreen()
  }
  onMounted(() => { document.addEventListener('fullscreenchange', sync); document.addEventListener('keydown', escape) })
  onBeforeUnmount(() => { disposed = true; closeWindowFullscreen(); document.removeEventListener('fullscreenchange', sync); document.removeEventListener('keydown', escape) })
  return { isFullscreen, fallbackFullscreen, toggleFullscreen }
}
