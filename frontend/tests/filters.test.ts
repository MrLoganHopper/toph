import {describe,it,expect} from 'vitest';
import {parseFilters,RANGE_LABELS} from '../src/features/logs/filterCore';
describe('URL filter state',()=>{
 it('has an explicit descending date default',()=>expect(parseFilters(new URLSearchParams(),'this_month')).toEqual({sort:'recorded_at',direction:'desc',range:'this_month'}));
 it.each(Object.keys(RANGE_LABELS))('round trips date range %s',range=>expect(parseFilters(new URLSearchParams({range}),'all').range).toBe(range));
 it('rejects an unrecognized preset',()=>expect(parseFilters(new URLSearchParams('range=tomorrow'),'today').range).toBe('today'));
 it('does not inherit JavaScript prototype keys as date presets',()=>expect(parseFilters(new URLSearchParams('range=toString'),'today').range).toBe('today'));
 it('keeps explicit date intervals separate from date presets',()=>expect(parseFilters(new URLSearchParams({from:'2026-09-01T00:00:00Z',to:'2026-09-03T00:00:00Z',range:'today'}),'all')).toEqual({sort:'recorded_at',direction:'desc',from:'2026-09-01T00:00:00Z',to:'2026-09-03T00:00:00Z'}));
 it('treats fertilizer and activity independently',()=>{const f=parseFilters(new URLSearchParams({activity_id:'a',fertilizer_id:'b',field_id:'c',employee_id:'d',tag_id:'e',direction:'asc'}),'all');expect(f).toMatchObject({activity_id:'a',fertilizer_id:'b',field_id:'c',employee_id:'d',tag_id:'e',direction:'asc'});});
 it('caps search length and never treats a cursor as a filter',()=>{const f=parseFilters(new URLSearchParams({q:'x'.repeat(240),cursor:'old-cursor'}),'all');expect(f.q).toHaveLength(200);expect(f).not.toHaveProperty('cursor');});
 it('does not propagate arbitrary sort expressions',()=>expect(parseFilters(new URLSearchParams('sort=DROP&direction=sideways'),'all')).toMatchObject({sort:'recorded_at',direction:'desc'}));
});
