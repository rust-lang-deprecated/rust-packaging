ifdef CFG_PACKAGE_NAME
  MSI = $(CFG_PACKAGE_NAME)-$(CFG_BUILD)
else
  MSI = rust
endif

FILEGROUPS=RustcGroup.wxs GccGroup.wxs DocsGroup.wxs CargoGroup.wxs
SRCS=rust.wxs $(FILEGROUPS)

RUSTCDIR ?= rustc
GCCDIR ?= rust-mingw
DOCSDIR ?= rust-docs
CARGODIR ?= cargo

OBJS=$(SRCS:.wxs=.wixobj)
# %WIX% variable contains path to WIX installdir (with trailing backslash) and is set by WiX installer
# heat.exe colects files info from directory recursively
HEAT="$(WIX)bin\heat.exe"
# candle.exe compiles wxs source file into wixobj file
CANDLE="$(WIX)bin\candle.exe"
# light.exe links wixobj files and creates msi
LIGHT="$(WIX)bin\light.exe"
RM ?= del

HEAT_FLAGS= -nologo -gg -sfrag -srd -sreg
CANDLE_FLAGS= -nologo -dRustcDir=$(RUSTCDIR) -dGccDir=$(GCCDIR) -dDocsDir=$(DOCSDIR) -dCargoDir=$(CARGODIR)
LIGHT_FLAGS= -nologo -ext WixUIExtension
ifeq ($(SVAL),1)
	LIGHT_FLAGS += -sval
endif

.SUFFIXES: .wxs .wixobj

all: $(MSI).msi

$(MSI).msi: $(OBJS)
	$(LIGHT) $(LIGHT_FLAGS) -out $@ $(OBJS) -sice:ICE57 
	# ICE57 wrongly complains about the shortcuts

.wxs.wixobj:
	$(CANDLE) $(CANDLE_FLAGS) -out $@ $^

RustcGroup.wxs:
	$(HEAT) dir $(RUSTCDIR) $(HEAT_FLAGS) -cg RustcGroup -dr Rustc -var var.RustcDir -out $@

GccGroup.wxs:
	$(HEAT) dir $(GCCDIR) $(HEAT_FLAGS) -cg GccGroup -dr Gcc -var var.GccDir -out $@

DocsGroup.wxs:
	$(HEAT) dir $(DOCSDIR) $(HEAT_FLAGS) -cg DocsGroup -dr Docs -var var.DocsDir -out $@ -t squash-components.xsl

CargoGroup.wxs:
	$(HEAT) dir $(CARGODIR) $(HEAT_FLAGS) -cg CargoGroup -dr Cargo -var var.CargoDir -out $@ -t remove-duplicates.xsl

clean:
	$(RM) $(MSI).msi $(OBJS) $(FILEGROUPS)
