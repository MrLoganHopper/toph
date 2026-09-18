import { lazy,Suspense,Component,type ReactNode } from 'react';
import { BrowserRouter,Routes,Route,Navigate } from 'react-router-dom';
import { QueryClient,QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider,Entry,Login,ChangePassword,FarmPicker,FarmGate } from './features/auth/Auth';
import { Shell } from './components/Shell';
import { Busy,ErrorBox } from './components/ui';
const DashboardPage = lazy(() => import('./features/dashboard/DashboardPage'));
const LogsPage = lazy(() => import('./features/logs/LogsPage'));
const MapPage = lazy(() => import('./features/map/MapPage'));
const EmployeesPage = lazy(() => import('./features/employees/EmployeesPage'));
const SchedulePage = lazy(() => import('./features/schedule/SchedulePage'));
const SettingsPage = lazy(() => import('./features/settings/SettingsPage'));
const WorkerHome = lazy(() => import('./features/worker/WorkerPages').then(m => ({default:m.WorkerHome})));
const WorkerRecord = lazy(() => import('./features/worker/WorkerPages').then(m => ({default:m.WorkerRecord})));
const client = new QueryClient({defaultOptions:{queries:{staleTime:15000,retry:1,refetchOnWindowFocus:true},mutations:{retry:false}}});
class Boundary extends Component<{children:ReactNode},{error:Error|null}> {
  state: {error:Error|null} = {error:null};
  static getDerivedStateFromError(error:Error) { return {error}; }
  render() { return this.state.error ? <main className="auth-page"><h1>TOPH</h1><ErrorBox error={this.state.error} retry={() => window.location.reload()}/></main> : this.props.children; }
}
export default function App() {
  return <Boundary><QueryClientProvider client={client}><BrowserRouter><AuthProvider><Suspense fallback={<Busy label="Opening page..."/>}><Routes>
    <Route path="/" element={<Entry/>}/><Route path="/login" element={<Login/>}/><Route path="/change-password" element={<ChangePassword/>}/><Route path="/select-farm" element={<FarmPicker/>}/>
    <Route path="/admin/:farmId" element={<FarmGate mode="admin"><Shell/></FarmGate>}><Route index element={<Navigate to="welcome" replace/>}/><Route path="welcome" element={<MapPage welcome/>}/><Route path="dashboard" element={<DashboardPage/>}/><Route path="logs" element={<LogsPage/>}/><Route path="map" element={<MapPage/>}/><Route path="employees" element={<EmployeesPage/>}/><Route path="schedule" element={<SchedulePage/>}/><Route path="settings" element={<SettingsPage/>}/></Route>
    <Route path="/worker/:farmId" element={<FarmGate mode="worker"/>}><Route index element={<WorkerHome/>}/><Route path="record" element={<WorkerRecord/>}/><Route path="history" element={<WorkerHome history/>}/></Route>
    <Route path="*" element={<Navigate to="/" replace/>}/>
  </Routes></Suspense></AuthProvider></BrowserRouter></QueryClientProvider></Boundary>;
}
