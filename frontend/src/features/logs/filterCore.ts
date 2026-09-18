import type {DateRange,LogFilters} from '../../api/types';
export const RANGE_LABELS:Record<DateRange,string>={all:'All time',today:'Today',this_week:'This week',this_month:'This month',last_day:'Last day',last_week:'Last week',last_month:'Last month'};
export function parseFilters(params:URLSearchParams,defaultRange:DateRange):LogFilters{
 const result:LogFilters={sort:'recorded_at',direction:params.get('direction')==='asc'?'asc':'desc'};
 const from=params.get('from'),to=params.get('to');
 if(from&&to){result.from=from;result.to=to;}else {const range=params.get('range') as DateRange|null;result.range=range&&Object.hasOwn(RANGE_LABELS,range)?range:defaultRange;}
 for(const key of ['employee_id','field_id','activity_id','fertilizer_id','tag_id','q'] as const){const value=params.get(key);if(value)result[key]=key==='q'?value.slice(0,200):value;}
 return result;
}
