/** Formatte un identifiant de semestre "AAAA-N" en libellé lisible. */
export function semesterLabel(semester: string): string {
  const [year, half] = semester.split('-')
  return `${year} — ${half === '1' ? 'S1' : 'S2'}`
}
