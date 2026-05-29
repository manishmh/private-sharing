/*
 * SCREENSHOT / CAPTURE DETERRENTS — BEST EFFORT, NOT A GUARANTEE.
 * ----------------------------------------------------------------
 * It is technically IMPOSSIBLE to reliably block screenshots or screen
 * recording from a mobile web browser. These measures only RAISE FRICTION:
 *   - block context menu / long-press-save / drag / text selection
 *   - blur + black overlay when the page is hidden or loses focus
 *     (catches app-switching, screen-record prompts on many devices)
 *   - desktop: detect PrintScreen and overwrite the clipboard + flash overlay
 * The PRIMARY, reliable protection is the per-client watermark baked into every
 * served image (visible tile + invisible LSB), so ANY capture is traceable.
 */

let installed = false

export function installDeterrents() {
  if (installed) return () => {}
  installed = true

  const prevent = (e) => { e.preventDefault(); return false }

  const onKeyUp = (e) => {
    // Desktop PrintScreen: try to clobber the clipboard with a notice + flash.
    if (e.key === 'PrintScreen' || e.code === 'PrintScreen') {
      try {
        navigator.clipboard?.writeText(
          'This content is confidential and watermarked to the recipient.'
        )
      } catch {}
      flashOverlay()
    }
  }

  document.addEventListener('contextmenu', prevent)
  document.addEventListener('dragstart', prevent)
  document.addEventListener('copy', prevent)
  document.addEventListener('keyup', onKeyUp)

  return () => {
    document.removeEventListener('contextmenu', prevent)
    document.removeEventListener('dragstart', prevent)
    document.removeEventListener('copy', prevent)
    document.removeEventListener('keyup', onKeyUp)
    installed = false
  }
}

function flashOverlay() {
  const el = document.getElementById('vault-capture-flash')
  if (!el) return
  el.style.opacity = '1'
  setTimeout(() => { el.style.opacity = '0' }, 900)
}

// Wire blur/visibility events to a setHidden(boolean) callback.
export function installVisibilityGuard(setHidden) {
  const hide = () => setHidden(true)
  const show = () => setHidden(false)
  const onVis = () => (document.hidden ? hide() : show())

  document.addEventListener('visibilitychange', onVis)
  window.addEventListener('blur', hide)
  window.addEventListener('focus', show)
  window.addEventListener('pagehide', hide)
  window.addEventListener('pageshow', show)

  return () => {
    document.removeEventListener('visibilitychange', onVis)
    window.removeEventListener('blur', hide)
    window.removeEventListener('focus', show)
    window.removeEventListener('pagehide', hide)
    window.removeEventListener('pageshow', show)
  }
}
