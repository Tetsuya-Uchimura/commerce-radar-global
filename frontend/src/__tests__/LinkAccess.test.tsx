import {describe,it,expect} from 'vitest';
import {render,screen} from '@testing-library/react';
import {LinkStatus,ProductLink,type LinkAccess} from '../LinkAccess';
const access=(status:LinkAccess['status']):LinkAccess=>({status,reason:'Observed response from server',scope:'server',checked_at:'2026-11-04T05:38:00Z',limitation:'Browser may differ'});
describe('product destination checks',()=>{
 it('labels the scope/date and only calls a checked response server reachable',()=>{
  const a=access('reachable');render(<><LinkStatus access={a}/><ProductLink access={a} url="https://store.com/products/item"/></>);
  expect(screen.getByText('Server reachable')).toBeInTheDocument();
  expect(screen.getByText(/Checked 2026-11-04T05:38:00 UTC/)).toBeInTheDocument();
  expect(screen.getByText(/your browser, location and login may differ/)).toBeInTheDocument();
  expect(screen.getByRole('link',{name:'Visit Store ↗'})).toHaveAttribute('href','https://store.com/products/item');
 });
 it('disables a confirmed broken destination instead of presenting a working store link',()=>{
  const a=access('unavailable');render(<><LinkStatus access={a}/><ProductLink access={a} url="https://tracker.com/disabled.html"/></>);
  expect(screen.getByText('Link unavailable')).toBeInTheDocument();
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
  expect(screen.getByText('Destination unavailable')).toHaveAttribute('aria-disabled','true');
 });
 it('labels a browser challenge without offering a misleading external link',()=>{
  const a=access('restricted');render(<><LinkStatus access={a}/><ProductLink access={a} url="https://tracker.com/product"/></>);
  expect(screen.getByText('Access restricted')).toBeInTheDocument();
  expect(screen.queryByRole('link',{name:'Visit Store ↗'})).not.toBeInTheDocument();
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
  expect(screen.getByText('Destination not verified · link disabled')).toHaveAttribute('aria-disabled','true');
 });
 it.each(['unconfirmed','login_required','rate_limited','unsafe'] as const)('does not navigate for %s',status=>{
  render(<ProductLink access={access(status)} url="https://tracker.com/product"/>);
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
 });
 it('does not navigate before a check exists',()=>{
  render(<ProductLink url="https://tracker.com/product"/>);
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
 });
 it('enables user-confirmed merchants with explicit manual-review scope',()=>{
  const a=access('user_confirmed');render(<><LinkStatus access={a}/><ProductLink access={a} url="https://buy.trychannel3.com/product"/></>);
  expect(screen.getByText('User-confirmed merchant')).toBeInTheDocument();
  expect(screen.getByText(/Representative product link checked in your browser/)).toBeInTheDocument();
  expect(screen.getByRole('link',{name:'Visit Store ↗'})).toBeInTheDocument();
  expect(screen.queryByText('Server reachable')).not.toBeInTheDocument();
 });

});
