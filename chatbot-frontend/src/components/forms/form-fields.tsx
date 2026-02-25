"use client";

import { ReactNode } from "react";
import { Control, FieldPath, FieldValues } from "react-hook-form";
import {
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type TextFieldProps<TFieldValues extends FieldValues> = {
  control: Control<TFieldValues>;
  name: FieldPath<TFieldValues>;
  label: string;
  placeholder?: string;
  description?: string;
  type?: "text" | "password" | "url";
  icon?: ReactNode;
};

export function RHFTextField<TFieldValues extends FieldValues>({
  control,
  name,
  label,
  placeholder,
  description,
  type = "text",
  icon,
}: TextFieldProps<TFieldValues>) {
  return (
    <FormField
      control={control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel className="text-sm font-semibold text-slate-800">{label}</FormLabel>
          <FormControl>
            <div className="relative">
              {icon ? (
                <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-slate-500 dark:text-slate-300">
                  {icon}
                </span>
              ) : null}
              <Input
                type={type}
                placeholder={placeholder}
                className={`h-11 bg-white ${icon ? "pl-10" : ""}`}
                {...field}
                value={(field.value as string) ?? ""}
              />
            </div>
          </FormControl>
          {description ? <FormDescription>{description}</FormDescription> : null}
          <FormMessage />
        </FormItem>
      )}
    />
  );
}

type SelectOption = {
  label: string;
  value: string;
};

type SelectFieldProps<TFieldValues extends FieldValues> = {
  control: Control<TFieldValues>;
  name: FieldPath<TFieldValues>;
  label: string;
  placeholder: string;
  options: SelectOption[];
  description?: string;
  icon?: ReactNode;
};

export function RHFSelectField<TFieldValues extends FieldValues>({
  control,
  name,
  label,
  placeholder,
  options,
  description,
  icon,
}: SelectFieldProps<TFieldValues>) {
  return (
    <FormField
      control={control}
      name={name}
      render={({ field }) => (
        <FormItem>
          <FormLabel className="text-sm font-semibold text-slate-800">{label}</FormLabel>
          <Select onValueChange={field.onChange} value={(field.value as string) ?? ""}>
            <FormControl>
              <div className="relative">
                {icon ? (
                  <span className="pointer-events-none absolute top-1/2 left-3 z-10 -translate-y-1/2 text-slate-500 dark:text-slate-300">
                    {icon}
                  </span>
                ) : null}
                <SelectTrigger className={`h-11 w-full bg-white ${icon ? "pl-10" : ""}`}>
                  <SelectValue placeholder={placeholder} />
                </SelectTrigger>
              </div>
            </FormControl>
            <SelectContent>
              {options.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {description ? <FormDescription>{description}</FormDescription> : null}
          <FormMessage />
        </FormItem>
      )}
    />
  );
}
