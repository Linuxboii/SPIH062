import { lazy, Suspense, useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import { DisclaimerBar, Nav, Footer, SkipLink } from './components/Shell'
import Landing from './pages/Landing'

/* Landing is eager — it is the entry point and must paint immediately.
   The assistant and the compound explorer (which carries the structure
   renderer) load on navigation, so the first view ships almost no JS. */
const Chat = lazy(() => import('./pages/Chat'))
const Compound = lazy(() => import('./pages/Compound'))
const Compounds = lazy(() => import('./pages/Compounds'))
const NotFound = lazy(() => import('./pages/NotFound'))

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    if (!window.location.hash) window.scrollTo(0, 0)
  }, [pathname])
  return null
}

function RouteFallback() {
  return (
    <div className="shell route-fallback">
      <div className="thinking">
        <span className="pulse" /><span className="pulse" /><span className="pulse" />
      </div>
    </div>
  )
}

export default function App() {
  return (
    <>
      <SkipLink />
      <DisclaimerBar />
      <Nav />
      <ScrollToTop />
      <main id="main" tabIndex={-1}>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/app" element={<Chat />} />
            <Route path="/compounds" element={<Compounds />} />
            <Route path="/compound/:id" element={<Compound />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </main>
      <Footer />
    </>
  )
}
