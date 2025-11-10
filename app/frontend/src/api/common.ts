export interface PostalAddress {
  street: string;
  city: string;
  state: string;
  postal_code: string;
}

export function formatPostalAddress(address: PostalAddress | null | undefined): string {
  if (!address) {
    return "";
  }

  const parts = [address.street, `${address.city}, ${address.state} ${address.postal_code}`];
  return parts.filter(Boolean).join("\n");
}
