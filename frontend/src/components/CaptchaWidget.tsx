import { useState, useEffect } from 'react'

interface CaptchaData {
  challenge_id: string
  question: string
}

interface CaptchaWidgetProps {
  onCaptcha: (id: string, answer: string) => void
}

export default function CaptchaWidget({ onCaptcha }: CaptchaWidgetProps) {
  const [captcha, setCaptcha] = useState<CaptchaData | null>(null)
  const [answer, setAnswer] = useState('')

  async function fetchCaptcha() {
    try {
      const res = await fetch('/api/auth/captcha')
      const data = await res.json()
      setCaptcha(data)
      onCaptcha(data.challenge_id, '') // reset parent state
      setAnswer('')
    } catch { /* ignore */ }
  }

  useEffect(() => { fetchCaptcha() }, [])

  useEffect(() => {
    if (captcha) onCaptcha(captcha.challenge_id, answer)
  }, [answer, captcha])

  if (!captcha) return null

  return (
    <div style={{
      background: 'var(--gray-50)', borderRadius: 'var(--radius)',
      padding: '12px 16px', marginBottom: 16,
      display: 'flex', alignItems: 'center', gap: 12,
    }}>
      <span style={{ fontWeight: 700, whiteSpace: 'nowrap' }}>{captcha.question}</span>
      <input
        type="text"
        value={answer}
        onChange={e => setAnswer(e.target.value)}
        placeholder="?"
        style={{
          width: 50, padding: '6px 8px', border: '1.5px solid var(--gray-300)',
          borderRadius: 6, textAlign: 'center', fontSize: '1rem',
        }}
      />
      <button type="button" onClick={fetchCaptcha}
        style={{
          background: 'none', border: 'none', cursor: 'pointer',
          fontSize: '1.3rem', padding: '4px 8px',
        }} title="Nouveau challenge">
        🔄
      </button>
    </div>
  )
}
