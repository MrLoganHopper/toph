import {describe,it,expect} from 'vitest';
import {toInstant,toLocalInput,dayBounds} from '../src/features/schedule/time';
describe('farm-local planned times',()=>{
 it('uses the farm zone, not the browser zone',()=>expect(toInstant('2026-09-17T12:00','America/Los_Angeles')).toBe('2026-09-17T19:00:00Z'));
 it('renders timestamps in a different farm zone',()=>expect(toLocalInput('2026-09-17T19:00:00Z','America/New_York')).toBe('2026-09-17T15:00'));
 it.each(['reject','earlier','later'] as const)('rejects a nonexistent spring time with %s disambiguation',choice=>expect(()=>toInstant('2026-03-08T02:30','America/Los_Angeles',choice)).toThrow());
 it('requires a choice for the repeated fall hour',()=>expect(()=>toInstant('2026-11-01T01:30','America/Los_Angeles')).toThrow());
 it('distinguishes both occurrences of the fall hour',()=>{expect(toInstant('2026-11-01T01:30','America/Los_Angeles','earlier')).toBe('2026-11-01T08:30:00Z');expect(toInstant('2026-11-01T01:30','America/Los_Angeles','later')).toBe('2026-11-01T09:30:00Z');});
 it.each([['2026-03-08',23],['2026-11-01',25]] as const)('calculates a %s local day correctly',(day,hours)=>{const b=dayBounds(day,'America/Los_Angeles');expect(Date.parse(b.to)-Date.parse(b.from)).toBe(hours*3600000);});
});
