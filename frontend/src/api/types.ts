import type { FeatureCollection,MultiPolygon,Polygon } from 'geojson';
export interface Named {id:string;name:string}
export interface Farm extends Named {timezone:string;created_at:string;updated_at:string}
export interface User extends Named {username:string;must_change_password:boolean}
export interface Membership {id:string;role:'admin'|'worker';is_enabled:boolean;farm:Farm}
export interface AuthResult {user:User;memberships:Membership[];csrf_token:string;must_change_password:boolean}
export interface Member {id:string;user_id:string;name:string;username:string;role:'admin'|'worker';is_enabled:boolean}
export interface MemberCreated {member:Member;temporary_password:string}
export interface Shift {id:string;employee:Named;start_at:string;end_at:string;field:Named|null;activity:Named|null;fertilizer:Named|null}
export interface ShiftInput {employee_id:string;start_at:string;end_at:string;field_id:string|null;activity_id:string|null;fertilizer_id:string|null}
export interface Bootstrap {user:User;farm:Farm;membership:Member;fields:Named[];activities:Named[];fertilizers:Named[];workers:Named[];tags:Named[];shifts:Shift[]}
export interface Page<T> {items:T[];next_cursor:string|null;total_matching:number}
export interface Turn {speaker:'worker'|'assistant';text:string;offset_ms:number}
export interface LogItem {id:string;recorded_at:string;employee:Named;activity:Named|null;fertilizer:Named|null;field:Named|null;scheduled_shift:{id:string;start_at:string;end_at:string}|null;summary_preview:string;extraction_confidence:number|null;tags:Named[]}
export interface LogDetail extends LogItem {summary:string;answers:{details:string|null;issues:string|null};recording:{id:string;content_type:string;duration_ms:number;waveform_peaks:number[]|null;transcript:Turn[];interview_version:string};field_geometry:Polygon|MultiPolygon|null}
export interface DashboardResult {as_of:string;timezone:string;metrics:{recordings_today:number;scheduled_workers_now:number;average_extraction_confidence:number|null;confidence_sample_size:number};metric_scopes:Record<string,string>;logs:Page<LogItem>}
export type DateRange='all'|'today'|'this_week'|'this_month'|'last_day'|'last_week'|'last_month';
export interface LogFilters {range?:DateRange;from?:string;to?:string;employee_id?:string;field_id?:string;activity_id?:string;fertilizer_id?:string;tag_id?:string;q?:string;sort?:'recorded_at';direction?:'asc'|'desc';limit?:number;cursor?:string}
export interface GeoCollection extends FeatureCollection<Polygon|MultiPolygon,{id:string;name:string}> {next_cursor:string|null;farm_bbox:number[]|null}
export interface FieldDetail extends Named {geometry:Polygon|MultiPolygon;created_at:string;updated_at:string}
export interface RecordingReceipt {id:string;recorded_at:string;uploaded_at:string|null;linked_log_id:string|null}
export interface RecordingDetail extends RecordingReceipt {content_type:string;size_bytes:number;duration_ms:number;transcript:Turn[];waveform_peaks:number[]|null;interview_version:string}
export interface UploadAuthorization {url:string;method:'POST';fields:Record<string,string>;expires_at:string;max_size_bytes:number}
export interface AudioAuthorization {url:string;expires_at:string;content_type:string;duration_ms:number}
export interface RealtimeSecret {client_secret:string;expires_at:number;model:string;interview_version:string}
