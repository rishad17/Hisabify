import { Plus } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { TransactionFormDialog } from '@/features/ledger/transaction-form-dialog'
import { cn } from '@/lib/utils'

export function AddTransactionButton({
  className,
  floating = false,
}: {
  className?: string
  /** Round floating action button for mobile screens. */
  floating?: boolean
}) {
  const [open, setOpen] = useState(false)
  return (
    <>
      {floating ? (
        <Button
          size="icon"
          onClick={() => setOpen(true)}
          aria-label="Add transaction"
          className={cn('size-14 rounded-full shadow-lg [&_svg:not([class*=size-])]:size-6', className)}
        >
          <Plus aria-hidden />
        </Button>
      ) : (
        <Button onClick={() => setOpen(true)} className={className}>
          <Plus aria-hidden /> Add transaction
        </Button>
      )}
      <TransactionFormDialog open={open} onOpenChange={setOpen} />
    </>
  )
}
