import { AppProviders } from './providers'
import { AppRouter } from './router'

export function App(): JSX.Element {
  return (
    <AppProviders>
      <AppRouter />
    </AppProviders>
  )
}
