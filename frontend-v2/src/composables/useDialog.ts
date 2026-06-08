import { reactive } from 'vue'

type DialogType = 'confirm' | 'prompt' | 'danger'

interface DialogState {
  visible: boolean
  type: DialogType
  title: string
  message: string
  confirmLabel: string
  cancelLabel: string
  inputPlaceholder: string
  inputValue: string
  resolve: ((v: string | boolean | null) => void) | null
}

export const dialogState = reactive<DialogState>({
  visible: false,
  type: 'confirm',
  title: '',
  message: '',
  confirmLabel: 'OK',
  cancelLabel: '',
  inputPlaceholder: '',
  inputValue: '',
  resolve: null,
})

function open(opts: {
  type?: DialogType
  title: string
  message?: string
  confirmLabel?: string
  cancelLabel?: string
  inputPlaceholder?: string
}): Promise<string | boolean | null> {
  return new Promise((resolve) => {
    dialogState.visible = true
    dialogState.type = opts.type ?? 'confirm'
    dialogState.title = opts.title
    dialogState.message = opts.message ?? ''
    dialogState.confirmLabel = opts.confirmLabel ?? 'OK'
    dialogState.cancelLabel = opts.cancelLabel ?? ''
    dialogState.inputPlaceholder = opts.inputPlaceholder ?? ''
    dialogState.inputValue = ''
    dialogState.resolve = resolve
  })
}

export function useDialog() {
  /** Confirm dialog → returns true / false */
  async function confirm(message: string, opts?: { title?: string; confirmLabel?: string; cancelLabel?: string; danger?: boolean }): Promise<boolean> {
    const result = await open({
      type: opts?.danger ? 'danger' : 'confirm',
      title: opts?.title ?? message,
      message: opts?.title ? message : '',
      confirmLabel: opts?.confirmLabel,
      cancelLabel: opts?.cancelLabel,
    })
    return result === true
  }

  /** Prompt dialog → returns string or null (cancelled) */
  async function prompt(message: string, opts?: { placeholder?: string; confirmLabel?: string; cancelLabel?: string }): Promise<string | null> {
    const result = await open({
      type: 'prompt',
      title: message,
      inputPlaceholder: opts?.placeholder,
      confirmLabel: opts?.confirmLabel,
      cancelLabel: opts?.cancelLabel,
    })
    if (result === null || result === false) return null
    return result as string
  }

  return { confirm, prompt }
}
