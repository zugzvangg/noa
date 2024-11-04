; RUN: if [ %llvmver -lt 16 ]; then %opt < %s %loadEnzyme -enzyme-preopt=false -enzyme -mem2reg -instsimplify -simplifycfg -S -enzyme-global-activity | FileCheck %s; fi
; RUN: %opt < %s %newLoadEnzyme -enzyme-preopt=false -passes="enzyme,function(mem2reg,instsimplify,%simplifycfg)" -S -enzyme-global-activity | FileCheck %s

; a function returning a ptr with no arguments is mistakenly marked as constant in spite of accessing a global

@global = external dso_local local_unnamed_addr global double*, align 8, !enzyme_shadow !{double** @dglobal}
@dglobal = external dso_local local_unnamed_addr global double*, align 8

; Function Attrs: noinline norecurse nounwind readonly uwtable
define dso_local double* @myglobal() local_unnamed_addr #0 {
entry:
  %ptr = load double*, double** @global, align 8
  ret double* %ptr
}

; Function Attrs: noinline norecurse nounwind readonly uwtable
define dso_local double @mulglobal(double %x) #0 {
entry:
  %call = tail call double* @myglobal()
  %arrayidx = getelementptr inbounds double, double* %call, i64 2
  %0 = load double, double* %arrayidx, align 8
  %mul = fmul fast double %0, %x
  ret double %mul
}

; Function Attrs: noinline nounwind uwtable
define dso_local double @derivative(double %x) local_unnamed_addr #1 {
entry:
  %0 = tail call double (...) @__enzyme_autodiff.f64(double (double)* nonnull @mulglobal, double %x) #2
  ret double %0
}

declare double @__enzyme_autodiff.f64(...) local_unnamed_addr

attributes #0 = { noinline norecurse nounwind readonly uwtable }
attributes #1 = { noinline nounwind uwtable }
attributes #2 = { nounwind }

; CHECK: define internal { double } @diffemulglobal(double %x, double %differeturn)
; CHECK-NEXT: entry:
; CHECK-NEXT:   %call_augmented = call { double*, double* } @augmented_myglobal()
; CHECK:   %call = extractvalue { double*, double* } %call_augmented, 0
; CHECK:   %"call'ac" = extractvalue { double*, double* } %call_augmented, 1
; CHECK-NEXT:   %"arrayidx'ipg" = getelementptr inbounds double, double* %"call'ac", i64 2
; CHECK-NEXT:   %arrayidx = getelementptr inbounds double, double* %call, i64 2
; CHECK-NEXT:   %0 = load double, double* %arrayidx, align 8
; CHECK-NEXT:   %[[m0diffe:.+]] = fmul fast double %differeturn, %x
; CHECK-NEXT:   %[[m1diffex:.+]] = fmul fast double %differeturn, %0
; CHECK-NEXT:   %[[i1:.+]] = load double, double* %"arrayidx'ipg", align 8
; CHECK-NEXT:   %[[i2:.+]] = fadd fast double %[[i1]], %[[m0diffe]]
; CHECK-NEXT:   store double %[[i2]], double* %"arrayidx'ipg", align 8
; CHECK:   %[[i3:.+]] = insertvalue { double } undef, double %[[m1diffex]], 0
; CHECK-NEXT:   ret { double } %[[i3]]
; CHECK-NEXT: }

; CHECK: define internal { double*, double* } @augmented_myglobal()
; CHECK-NEXT: entry:
; CHECK-NEXT:   %0 = alloca { double*, double* }
; CHECK-NEXT:   %"ptr'ipl" = load double*, double** @dglobal, align 8
; CHECK-NEXT:   %ptr = load double*, double** @global, align 8
; CHECK-NEXT:   %[[a2:.+]] = getelementptr inbounds { double*, double* }, { double*, double* }* %0, i32 0, i32 0
; CHECK-NEXT:   store double* %ptr, double** %[[a2]]
; CHECK-NEXT:   %[[a3:.+]] = getelementptr inbounds { double*, double* }, { double*, double* }* %0, i32 0, i32 1
; CHECK-NEXT:   store double* %"ptr'ipl", double** %[[a3]]
; CHECK-NEXT:   %[[a4:.+]] = load { double*, double* }, { double*, double* }* %0
; CHECK-NEXT:   ret { double*, double* } %[[a4]]
; CHECK-NEXT: }

; CHECK: define internal void @diffemyglobal()
; CHECK-NEXT: entry:
; CHECK-NEXT:   ret void
; CHECK-NEXT: }
