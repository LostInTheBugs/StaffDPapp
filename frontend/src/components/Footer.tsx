export default function Footer() {
  return (
    <footer style={{
      background: 'var(--blue)',
      color: 'rgba(255,255,255,0.7)',
      padding: '8px 24px',
      fontSize: '.75rem',
      textAlign: 'center',
      position: 'fixed',
      bottom: 0,
      left: 0,
      right: 0,
      zIndex: 100,
      display: 'flex',
      justifyContent: 'center',
      gap: 24,
    }}>
      <span>StaffDPapp v2026.07.001</span>
      <a href="https://github.com/LostInTheBugs/StaffDPapp" target="_blank" rel="noopener noreferrer"
        style={{ color: 'rgba(255,255,255,0.7)', textDecoration: 'underline' }}>
        GitHub
      </a>
      <span>Art. L.412-1 · L.415-5 — Luxembourg 🇱🇺</span>
    </footer>
  )
}
