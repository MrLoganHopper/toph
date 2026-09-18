import {Temporal} from '@js-temporal/polyfill';
export type Disambiguation='reject'|'earlier'|'later';
export function toInstant(value:string,zone:string,disambiguation:Disambiguation='reject'){
 try{const plain=Temporal.PlainDateTime.from(value);const zoned=plain.toZonedDateTime(zone,{disambiguation});if(!zoned.toPlainDateTime().equals(plain))throw new Error('Nonexistent local time');return zoned.toInstant().toString();}
 catch{throw new Error(`The local time ${value} is invalid or occurs twice in ${zone}. Choose a valid time, or select first/second occurrence for a repeated clock time.`);}
}
export function toLocalInput(value:string,zone:string){return Temporal.Instant.from(value).toZonedDateTimeISO(zone).toPlainDateTime().toString({smallestUnit:'minute'});}
export function localToday(zone:string){return Temporal.Now.zonedDateTimeISO(zone).toPlainDate().toString();}
export function dayBounds(value:string,zone:string){const day=Temporal.PlainDate.from(value);return {from:day.toZonedDateTime(zone).toInstant().toString(),to:day.add({days:1}).toZonedDateTime(zone).toInstant().toString()};}
