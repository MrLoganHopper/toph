import {useEffect,useRef,useState} from 'react';
import maplibregl,{type GeoJSONSource,type Map as LibreMap,type StyleSpecification,type LngLatBoundsLike} from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type {GeoCollection} from '../../api/types';
interface Props{data?:GeoCollection;selectedId?:string|null;onSelect?:(id:string|null)=>void;onReady?:()=>void;className?:string;}
function positions(value:unknown):[number,number][]{if(!Array.isArray(value))return [];if(typeof value[0]==='number'&&typeof value[1]==='number')return [[value[0],value[1]]];return value.flatMap(positions);}
function bounds(data:GeoCollection,selected?:string|null):LngLatBoundsLike|null{
 if(!selected&&data.farm_bbox?.length===4)return data.farm_bbox as [number,number,number,number];
 const features=selected?data.features.filter(f=>f.properties.id===selected):data.features;
 const points=features.flatMap(f=>positions(f.geometry.coordinates));if(!points.length)return null;
 return points.reduce<[number,number,number,number]>((b,p)=>[Math.min(b[0],p[0]),Math.min(b[1],p[1]),Math.max(b[2],p[0]),Math.max(b[3],p[1])],[Infinity,Infinity,-Infinity,-Infinity]);
}
export default function FieldMap(props:Props){
 const host=useRef<HTMLDivElement>(null),instance=useRef<LibreMap|null>(null),latest=useRef(props);latest.current=props;
 const [error,setError]=useState('');const configured=!!import.meta.env.VITE_MAP_STYLE_URL;
 const update=()=>{const map=instance.current;const p=latest.current;if(!map?.getSource('fields')||!p.data)return;(map.getSource('fields') as GeoJSONSource).setData(p.data);map.setPaintProperty('field-fill','fill-opacity',['case',['==',['get','id'],p.selectedId||''],0.34,['boolean',['feature-state','hover'],false],0.24,0.12]);map.setPaintProperty('field-line','line-width',['case',['==',['get','id'],p.selectedId||''],3.5,['boolean',['feature-state','hover'],false],3,2]);const fit=bounds(p.data,p.selectedId);if(fit)map.fitBounds(fit,{padding:45,maxZoom:16,duration:window.matchMedia('(prefers-reduced-motion: reduce)').matches?0:700});};
 const updateRef=useRef(update);updateRef.current=update;
 useEffect(()=>{if(!host.current)return;let alive=true;let map:LibreMap|undefined;let popup:maplibregl.Popup|undefined;let resize:ResizeObserver|undefined;let hovered:string|null=null;
  try{const neutral:StyleSpecification={version:8,sources:{},layers:[{id:'neutral-background',type:'background',paint:{'background-color':'#dde4dc'}}]};map=new maplibregl.Map({container:host.current,style:import.meta.env.VITE_MAP_STYLE_URL||neutral,center:[-93.1,41.2],zoom:11,attributionControl:false});instance.current=map;map.addControl(new maplibregl.AttributionControl({compact:true}),'bottom-left');map.addControl(new maplibregl.NavigationControl({showCompass:false}),'bottom-right');
  map.on('load',()=>{if(!alive||!map)return;map.addSource('fields',{type:'geojson',promoteId:'id',data:latest.current.data||{type:'FeatureCollection',features:[]}});map.addLayer({id:'field-fill',type:'fill',source:'fields',paint:{'fill-color':'#ffffff','fill-opacity':0.16}});map.addLayer({id:'field-line',type:'line',source:'fields',paint:{'line-color':configured?'#ffffff':'#35584a','line-width':2}});updateRef.current();latest.current.onReady?.();});
  map.on('click',event=>{if(!map?.getLayer('field-fill'))return;const feature=map.queryRenderedFeatures(event.point,{layers:['field-fill']})[0];latest.current.onSelect?.(feature?String(feature.properties.id):null);});
  map.on('mousemove','field-fill',event=>{if(!map)return;map.getCanvas().style.cursor=latest.current.onSelect?'pointer':'grab';const feature=event.features?.[0];if(feature){const id=String(feature.properties.id);if(hovered!==id){if(hovered)map.setFeatureState({source:'fields',id:hovered},{hover:false});map.setFeatureState({source:'fields',id},{hover:true});hovered=id;}popup??=new maplibregl.Popup({closeButton:false,closeOnClick:false});popup.setLngLat(event.lngLat).setText(String(feature.properties.name)).addTo(map);}});
  map.on('mouseleave','field-fill',()=>{if(map){map.getCanvas().style.cursor='';if(hovered)map.setFeatureState({source:'fields',id:hovered},{hover:false});}hovered=null;popup?.remove();});
  map.on('error',()=>{if(alive){setError('Satellite imagery could not load. Check the style URL, token restrictions, and network.');latest.current.onReady?.();}});
  resize=new ResizeObserver(()=>map?.resize());resize.observe(host.current);
  }catch{setError('Interactive maps need WebGL. Use the field selector below or open this page in another browser.');latest.current.onReady?.();}
  return()=>{alive=false;resize?.disconnect();popup?.remove();map?.remove();instance.current=null;};
 },[]);
 useEffect(()=>{updateRef.current();},[props.data,props.selectedId]);
 return <div className={`field-map ${props.className||''}`} data-testid="field-map"><div ref={host} className="map-canvas" aria-label="Farm field boundary map"/>{(!configured||error||props.data?.features.length===0)&&<div className="map-warning" role="status">{error||(!configured?'Satellite style is not configured. Showing the farm boundaries on a neutral background.':'No fields yet. Add a GeoJSON boundary in Settings.')}</div>}</div>;
}
