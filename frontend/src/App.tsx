import { Switch, Route, Router as WouterRouter } from "wouter";
import RunsList from "./pages/RunsList";
import RunDetail from "./pages/RunDetail";

function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-gray-900">404</h1>
        <p className="mt-1 text-sm text-gray-500">Page not found</p>
      </div>
    </div>
  );
}

function Router() {
  return (
    <Switch>
      <Route path="/" component={RunsList} />
      <Route path="/runs/:id" component={RunDetail} />
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, "")}>
      <Router />
    </WouterRouter>
  );
}

export default App;
