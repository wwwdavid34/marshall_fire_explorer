import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "leaflet/dist/leaflet.css";
import "./App.css";
import { TitleBar } from "./components/TitleBar";
import { ParcelMap } from "./components/ParcelMap";
import { MapControls } from "./components/MapControls";
import { DetailPanel } from "./components/DetailPanel";

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TitleBar />
      <div className="app-layout">
        <div className="map-area">
          <ParcelMap />
          <MapControls />
        </div>
        <DetailPanel />
      </div>
    </QueryClientProvider>
  );
}

export default App;
