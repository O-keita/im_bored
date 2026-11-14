import { useCallback, useLayoutEffect, useRef, useState, type MouseEvent, type ReactNode } from 'react'

/** Width of an element, tracked as it resizes, so SVG charts can lay out in real pixels. */
export function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(0)
  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    observer.observe(element)
    return () => observer.disconnect()
  }, [])
  return [ref, width]
}

interface TipState {
  x: number
  y: number
  content: ReactNode
}

/** A tooltip that follows the pointer. Render `tip` once, call `show` and `hide` from marks. */
export function useTip() {
  const [state, setState] = useState<TipState | null>(null)
  const show = useCallback(
    (event: MouseEvent, content: ReactNode) => setState({ x: event.clientX, y: event.clientY, content }),
    [],
  )
  const hide = useCallback(() => setState(null), [])
  const flip = state !== null && state.x > window.innerWidth - 240
  const tip = state && (
    <div className="tip" role="tooltip" style={{ left: state.x, top: state.y, transform: `translate(${flip ? 'calc(-100% - 14px)' : '14px'}, -50%)` }}>
      {state.content}
    </div>
  )
  return { tip, show, hide }
}
