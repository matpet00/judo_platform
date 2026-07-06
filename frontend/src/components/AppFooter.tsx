export function AppFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="app-footer">
      <span>Judo klub Orlová {year}</span>
    </footer>
  );
}
